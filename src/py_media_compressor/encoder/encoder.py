import os
from enum import Enum, auto, unique
from queue import Queue
from threading import Thread
from typing import List, Tuple
import bitmath
import ffmpeg
from tqdm import tqdm

from py_media_compressor.common import progress
from py_media_compressor import log
from py_media_compressor import utils
from py_media_compressor.utils import pformat

PROCESSER_NAME = "Automatic media compression processed"


@unique
class FileTaskState(Enum):
    INIT = auto()
    WAIT = auto()
    SKIPPED = auto()
    SUCCESS = auto()
    ERROR = auto()

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_


def media_compress_encode(inputFilepath: str, outputFilepath: str, isForce=False, maxHeight=1440, removeErrorOutput=True, useProgressbar=False, leave=True) -> FileTaskState:
    """미디어를 압축합니다.

    Args:
        inputFilepath (str): 미디어 파일 경로
        outputFilepath (str): 출력 파일 경로
        isForce (bool, optional): 이미 처리된 미디어 파일을 강제적으로 재처리합니다. Defaults to False.
        maxHeight (int, optional): 미디어의 최대 세로 픽셀. Defaults to 1440.
        removeErrorOutput (bool, optional): 정상적으로 압축하지 못했을 경우 출력 파일을 삭제합니다. Defaults to True.
        useProgressbar (bool, optional): 진행바 사용 여부. Defaults to False.
        leave (bool, optional): 중첩된 진행바를 사용할 경우, False 를 권장합니다. Defaults to True.

    Returns:
        bool: 작업 완료 상태
    """

    logger = log.get_logger(media_compress_encode)

    if not os.path.isfile(inputFilepath):
        logger.error(f"입력 파일이 존재하지 않습니다. Filepath: {inputFilepath}")
        return FileTaskState.ERROR

    probe = ffmpeg.probe(inputFilepath)
    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)

    is_only_audio = video_stream == None

    output_dirpath = os.path.dirname(outputFilepath)
    os.makedirs(output_dirpath, exist_ok=True)

    ffmpeg_global_args = {}

    if is_only_audio:
        format = "ipod"  # == m4a
        ext = ".m4a"
    else:
        ffmpeg_global_args["c:v"] = "libx264"
        ffmpeg_global_args["crf"] = 20
        ffmpeg_global_args["preset"] = "veryslow"
        format = "mp4"
        ext = ".mp4"
        height = int(video_stream["height"])
        if height > maxHeight:
            is_even = round(int(video_stream["width"]) * maxHeight / height) % 2 == 0
            ffmpeg_global_args["vf"] = f"scale={'-1' if is_even else '-2'}:{maxHeight}"

    ffmpeg_global_args["filename"] = f"{os.path.splitext(outputFilepath)[0]}{ext}"
    ffmpeg_global_args["format"] = format

    # * 영상 메타데이터에 표식 추가
    comment = ""

    if "format" in probe and (tags := probe["format"].get("tags", None)) != None:
        for c in (tags.get("comment", ""), tags.get("COMMENT", ""), tags.get("Comment", "")):
            if not utils.is_str_empty_or_space(c):
                comment = c
                break

    comment_lines = comment.splitlines(keepends=False)

    if len(comment_lines) == 0 or comment_lines[-1] != PROCESSER_NAME:
        if comment == "":
            comment = PROCESSER_NAME
        else:
            comment = f"{comment}\n{PROCESSER_NAME}"
        ffmpeg_global_args["metadata"] = f"comment={comment}"
    else:
        # * 영상이 이미 처리된 경우
        logger.info("이미 처리된 미디어입니다.")
        if isForce:
            logger.warning(f"강제로 재인코딩을 실시합니다... is_force: {isForce}")
        else:
            return FileTaskState.SKIPPED

    audio_stream_info = None

    for stream_info in (stream for stream in probe["streams"] if stream["codec_type"] == "audio"):
        if audio_stream_info == None or stream_info["channels"] > audio_stream_info["channels"]:
            audio_stream_info = stream_info

    if audio_stream_info != None:
        if stream_info["codec_name"] in ["aac", "mp3"]:
            ffmpeg_global_args["c:a"] = "copy"
        else:
            ffmpeg_global_args["c:a"] = "aac"
            bit_rate = stream_info.get("bit_rate", None)
            ffmpeg_global_args["b:a"] = 320_000 if bit_rate == None else int(bit_rate)

    stream = ffmpeg.input(inputFilepath)

    stream = ffmpeg.output(stream, **ffmpeg_global_args)

    stream = ffmpeg._ffmpeg.global_args(stream, "-hide_banner")

    stream = ffmpeg.overwrite_output(stream)

    def msg_reader(queue: Queue, temp_msg_storage: List = None):
        total_duration = float(probe["format"]["duration"])
        bar = tqdm(total=round(total_duration, 2), leave=leave)
        info = {}

        for msg in iter(queue.get, None):
            if msg["type"] == "stderr":
                if logger.isEnabledFor(log.DEBUG):
                    logger.debug(f"ffmpeg output str: \n{pformat(msg)}")
                if temp_msg_storage != None:
                    temp_msg_storage.append(msg["msg"])

            elif msg["type"] == "stdout":
                update_value = None
                if "out_time_ms" in msg:
                    time = max(round(float(msg["out_time_ms"]) / 1000000.0, 2), 0)
                    update_value = time - bar.n
                elif "progress" in msg and msg["progress"] == "end":
                    update_value = bar.total - bar.n

                for key, value in msg.items():
                    if key in ["frame", "fps", "total_size", "bitrate", "out_time", "speed", "dup_frames", "drop_frames"]:
                        if key == "total_size":
                            value = bitmath.best_prefix(int(value), system=bitmath.SI)
                        elif key == "out_time":
                            value = value.split(".")[0]
                        elif key == "dup_frames" and value == "0":
                            continue
                        elif key == "drop_frames" and value == "0":
                            continue

                        info[key] = value

                if update_value != None:
                    bar.set_postfix(info, refresh=False)
                    bar.update(update_value)
                else:
                    bar.set_postfix(info)

        bar.close()

    def error_output_check(result: FileTaskState):
        if removeErrorOutput and result == FileTaskState.ERROR and os.path.isfile(ffmpeg_global_args["filename"]):
            os.remove(ffmpeg_global_args["filename"])
            logger.info(f"오류가 발생한 출력파일을 제거했습니다. Path: {ffmpeg_global_args['filename']}")
        return result

    logger.info(f"ffmpeg Arguments: \n[ffmpeg {' '.join(ffmpeg.get_args(stream))}]")

    if useProgressbar:
        msg_queue = Queue()
        temp_msg_storage = []
        try:
            process = progress.run_ffmpeg_process_with_msg_queue(stream, msg_queue)
            utils.set_low_process_priority(process.pid)
            logger.debug(f"ffmpeg Arguments: \n[ffmpeg {' '.join(ffmpeg.get_args(stream))}]")

            Thread(target=msg_reader, args=[msg_queue, temp_msg_storage]).start()

            if process.wait() != 0:
                raise Exception("프로세스가 올바르게 종료되지 않았습니다.")

            utils.set_file_permission(ffmpeg_global_args["filename"])
            return FileTaskState.SUCCESS

        except Exception as err:
            logger.error(f"미디어 처리 오류: \n{pformat(temp_msg_storage)}\n{err}")
            utils.set_file_permission(ffmpeg_global_args["filename"])
            return error_output_check(FileTaskState.ERROR)
    else:
        try:
            process = ffmpeg.run_async(stream_spec=stream, pipe_stdout=True, pipe_stderr=True)
            _, stderr = process.communicate()
            utils.set_low_process_priority(process.pid)

            if process.poll() != 0:
                raise ffmpeg.Error("ffmpeg", "", stderr)

            logger.info(utils.string_decode(stderr))
            utils.set_file_permission(ffmpeg_global_args["filename"])
            return FileTaskState.SUCCESS

        except ffmpeg.Error as err:
            logger.error(utils.string_decode(err.stderr))
            utils.set_file_permission(ffmpeg_global_args["filename"])
            return error_output_check(FileTaskState.ERROR)


def get_output_fileext(filepath: str):

    assert os.path.isfile(filepath), "파일이 존재하지 않습니다."

    probe = ffmpeg.probe(filepath)
    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
    return ".m4a" if video_stream == None else ".mp4"


def get_source_file(inputPaths: List[str], mediaExtFilter: List[str] = None, useProgressbar=False, leave=True) -> Tuple[List, int, int]:
    """입력 경로에서 소스파일을 검색합니다.

    Args:
        inputPaths (List[str]): 입력 경로
        mediaExtFilter (List[str], optional): 미디어 확장자 필터. Defaults to None.
        useProgressbar (bool, optional): 진행바 사용 여부. Defaults to False.
        leave (bool, optional): 중첩된 진행바를 사용할 경우, False 를 권장합니다. Defaults to True.

    Returns:
        Tuple[List, int, int]: 검색된 소스 파일 리스트, 검색된 파일 수, 중복 소스 파일 수
    """

    logger = log.get_logger(get_source_file)

    temp_hash_dupl_list = []

    def duplicate_file_filter(path: str, tqdm_manager: tqdm = None):
        is_dupl = False
        dupl_info = None
        fileinfo = {"input_file": path, "input_file_size": os.path.getsize(path)}

        if isinstance(tqdm_manager, tqdm):
            tqdm_manager.set_description("[DupCheck] 중복 파일 확인 중...")

        for o_fileinfo in temp_hash_dupl_list:
            if fileinfo["input_file"] == o_fileinfo["input_file"]:  # 경로가 겹치는 경우 (1차 필터링)
                is_dupl = True
                dupl_info = o_fileinfo
                break
            elif fileinfo["input_file_size"] == o_fileinfo["input_file_size"]:  # 파일 크기가 겹치는 경우 (2차 필터링)
                if isinstance(tqdm_manager, tqdm):
                    tqdm_manager.set_description("[DupCheck] MD5 해시 계산 중...")

                fileinfo["input_md5_hash"] = utils.get_MD5_hash(fileinfo["input_file"])

                if "input_md5_hash" not in o_fileinfo:
                    o_fileinfo["input_md5_hash"] = utils.get_MD5_hash(o_fileinfo["input_file"])

                if fileinfo["input_md5_hash"] == o_fileinfo["input_md5_hash"]:  # MD5 해시가 겹치는 경우 (3차 필터링)
                    is_dupl = True
                    dupl_info = o_fileinfo
                    break

        if isinstance(tqdm_manager, tqdm):
            if is_dupl:
                tqdm_manager.set_description("[DupCheck] 중복 파일 감지됨")
            else:
                tqdm_manager.set_description("[DupCheck] 확인 완료")

        if not is_dupl:
            temp_hash_dupl_list.append(fileinfo)
        return (not is_dupl, fileinfo, dupl_info)

    file_count = 0
    dupl_file_count = 0
    source_infos = []

    input_iter = tqdm(inputPaths, desc="입력 경로에서 파일 검색 중...", leave=leave) if useProgressbar else inputPaths
    for input_filepath in input_iter:
        if useProgressbar:
            input_iter.set_postfix(input_filepath=input_filepath)

        input_filepath = os.path.normpath(input_filepath)
        detected_fileinfos = []

        media_files = utils.get_media_files(input_filepath, mediaExtFilter=mediaExtFilter)
        media_files_iter = tqdm(media_files, leave=False) if useProgressbar else media_files
        for detected_filepath in media_files_iter:
            if useProgressbar:
                media_files_iter.set_postfix(filepath=detected_filepath.replace(input_filepath, ""))

            if (dupl_test_result := duplicate_file_filter(detected_filepath, tqdm_manager=media_files_iter if useProgressbar else None))[0]:
                detected_fileinfos.append(dupl_test_result[1])
                file_count += 1
            else:
                logger.info(f"중복 파일이 제외되었습니다.\nOrigin: {pformat(dupl_test_result[1])}\nTest: {pformat(dupl_test_result[2])}", {"dest": log.LogDestination.FILE})
                dupl_file_count += 1

        if len(detected_fileinfos) > 0:
            source_infos.append({"target": input_filepath, "files": detected_fileinfos})

    return (source_infos, file_count, dupl_file_count)
