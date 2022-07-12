import os
from enum import Enum, auto, unique
from pprint import pformat
from queue import Queue
import shutil
from threading import Thread
from typing import List
import bitmath
import ffmpeg
from tqdm import tqdm

from py_media_compressor.common import progress
from py_media_compressor import log
from py_media_compressor import utils

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
        input_filepath (str): 미디어 파일 경로
        output_dirpath (str): 출력 파일 경로
        is_force (bool, optional): 이미 처리된 미디어 파일을 강제적으로 재처리합니다. Defaults to False.
        max_height (int, optional): 미디어의 최대 세로 픽셀. Defaults to 1440.
        removeErrorOutput (bool, optional): 정상적으로 압축하지 못했을 경우 출력 파일을 삭제합니다. Defaults to True.
        useProgressbar (bool, optional): 진행바 사용 여부. Defaults to False.
        leave (bool, optional): 중첩된 진행바를 사용할 경우, False 를 권장합니다. Defaults to True.

    Returns:
        bool: 작업 완료 상태
    """

    logger = log.get_logger(name=f"{os.path.splitext(os.path.basename(__file__))[0]}.main")

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
    tags = probe["format"]["tags"]
    comment = ""

    for c in (tags.get("comment", ""), tags.get("COMMENT", "")):
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

    if useProgressbar:
        msg_queue = Queue()
        temp_msg_storage = []
        try:
            process = progress.run_ffmpeg_process_with_msg_queue(stream, msg_queue)
            logger.debug(f"ffmpeg Arguments: \n[ffmpeg {' '.join(ffmpeg.get_args(stream))}]")

            Thread(target=msg_reader, args=[msg_queue, temp_msg_storage]).start()

            if process.wait() != 0:
                raise Exception("프로세스가 올바르게 종료되지 않았습니다.")

            return FileTaskState.SUCCESS
        except Exception as err:
            logger.error(f"미디어 처리 오류: \n{pformat(temp_msg_storage)}\n{err}")
            return error_output_check(FileTaskState.ERROR)
    else:
        logger.debug(f"ffmpeg Arguments: \n[ffmpeg {' '.join(ffmpeg.get_args(stream))}]")

        try:
            _, stderr = ffmpeg.run(stream_spec=stream, capture_stdout=True, capture_stderr=True)
            logger.info(utils.string_decode(stderr))
            return FileTaskState.SUCCESS
        except ffmpeg.Error as err:
            logger.error(utils.string_decode(err.stderr))
            return error_output_check(FileTaskState.ERROR)


def get_output_fileext(filepath: str):

    assert os.path.isfile(filepath), "파일이 존재하지 않습니다."

    probe = ffmpeg.probe(filepath)
    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
    return ".m4a" if video_stream == None else ".mp4"


def main():
    import argparse
    from pprint import pformat

    parser = argparse.ArgumentParser(description="미디어를 압축 인코딩합니다.")

    parser.add_argument("--log-level", choices=log.LOGLEVEL_DICT.keys(), dest="log_level", default="info", help="로그 레벨 설정")
    parser.add_argument("--log-mode", choices=["c", "f", "cf", "console", "file", "consolefile"], dest="log_mode", default="consolefile", help="로그 출력 모드 설정")
    parser.add_argument("--log-path", dest="log_path", default=log.SETTINGS["dir"], help="로그 출력 모드 설정")
    parser.add_argument("-i", dest="input", action="append", required=True, help="하나 이상의 입력 소스 파일 및 디렉토리 경로")
    parser.add_argument("-o", dest="output", default="out", help="출력 디렉토리 경로")
    parser.add_argument("-r", "--replace", dest="replace", action="store_true", help="원본 파일보다 작을 경우, 원본 파일을 덮어씁니다. 아닐경우, 출력파일이 삭제됩니다.")
    parser.add_argument("-e", "--already_exists_mode", choices=["overwrite", "skip", "numbering"], dest="already_exists_mode", default="numbering", help="출력 폴더에 같은 이름의 파일이 있을 경우, 사용할 모드.")
    parser.add_argument("-s", "--save_error_output", dest="save_error_output", action="store_true", help="오류가 발생한 출력물을 제거하지 않습니다.")
    parser.add_argument("-f", "--force", dest="force", action="store_true", help="이미 압축된 미디어 파일을 스킵하지 않고, 재압축합니다.")
    parser.add_argument("--height", dest="height", default=1440, help="출력 비디오 스트림의 최대 세로 픽셀 수를 설정합니다.")

    args = vars(parser.parse_args())

    log.SETTINGS["level"] = log.LOGLEVEL_DICT[args["log_level"].lower()]
    log.SETTINGS["use_console"] = args["log_mode"] in ["c", "cf", "console", "consolefile"]
    log.SETTINGS["use_rotatingfile"] = args["log_mode"] in ["f", "cf", "file", "consolefile"]

    if args["log_path"] != "" and not args["log_path"].isspace():
        log.SETTINGS["dir"] = args["log_path"]

    logger = log.get_logger(name=f"{os.path.splitext(os.path.basename(__file__))[0]}.main")

    logger.info("** 프로그램 시작점 **")
    logger.debug(f"입력 인수: {args}")

    for info in (utils.check_command_availability("ffmpeg -version"), utils.check_command_availability("ffprobe -version")):
        if not info[0] or logger.isEnabledFor(log.DEBUG):
            info_str = pformat(
                {
                    "exit_success": info[0],
                    "stdout": utils.string_decode(info[1]).splitlines(),
                    "stderr": utils.string_decode(info[2]).splitlines(),
                    "exception": info[3],
                }
            )

        if not info[0]:
            logger.critical(f"ffmpeg 또는 ffprobe 동작 확인 불가, 해당 프로그램은 ffmpeg 및 ffprobe가 필요합니다.\nInfo: {info_str}")
            return

        if logger.isEnabledFor(log.DEBUG):
            logger.debug(f"command 실행 가능 여부, 검사 정보: {info_str}")

    logger.debug(f"ffmpeg, ffprobe 동작 확인 완료")

    # 입력 소스 파일 추출 및 중복 제거
    file_count = 0
    dupl_file_count = 0
    source_infos = []
    temp_path_dupl_list = []
    temp_hash_dupl_list = []
    for input_filepath in args["input"]:
        input_filepath = os.path.normpath(input_filepath)
        detected_fileinfos = []

        for detected_filepath in utils.get_media_files(input_filepath):
            if detected_filepath not in temp_path_dupl_list:  # 경로가 겹치는 경우 (1차 필터링)
                temp_path_dupl_list.append(detected_filepath)

                filehash = utils.get_MD5_hash(detected_filepath)
                if filehash not in temp_hash_dupl_list:  # MD5 해시가 겹치는 경우 (2차 필터링)
                    temp_hash_dupl_list.append(filehash)

                    detected_fileinfos.append({"input_file": detected_filepath, "input_md5_hash": filehash})
                    file_count += 1
                    continue

            dupl_file_count += 1

        if len(detected_fileinfos) > 0:
            source_infos.append({"target": input_filepath, "files": detected_fileinfos})

    logger.debug(f"입력 소스파일: \n{pformat(source_infos)}")
    logger.info(f"감지된 소스파일 수: {dupl_file_count + file_count}, 입력 소스파일 수: {file_count}, 중복 소스파일 수: {dupl_file_count}")

    output_dirpath = args["output"]
    logger.info(f"출력 디렉토리: {output_dirpath}")
    os.makedirs(output_dirpath, exist_ok=True)

    log.LogDest = log.LogDestination.FILE

    is_replace = args["replace"]
    is_force = args["force"]
    is_save_error_output = args["save_error_output"]
    already_exists_mode = args["already_exists_mode"]

    for source_info in tqdm(source_infos):
        logger.debug(f"현재 작업 소스 정보: \n{pformat(source_info)}")

        for fileinfo in (fileinfo_tqdm := tqdm(source_info["files"], leave=False)):
            fileinfo_tqdm.set_postfix(filename=os.path.basename(fileinfo["input_file"]))
            logger.info(f"현재 작업 파일 정보: \nInput Filepath: {fileinfo['input_file']}\nInput File MD5 Hash: {fileinfo['input_md5_hash']}")

            try:
                ext = get_output_fileext(fileinfo["input_file"])
            except Exception:
                logger.error("출력 파일 확장자를 추정할 수 없습니다. 해당 파일을 건너뜁니다.")
                continue

            fileinfo["output_file"] = os.path.join(output_dirpath, f"{os.path.splitext(os.path.basename(fileinfo['input_file']))[0]}{ext}")

            if already_exists_mode == "numbering":
                count = 0
                output_filepath = fileinfo["output_file"]
                temp_filename = os.path.splitext(output_filepath)[0]
                while os.path.isfile(output_filepath):
                    output_filepath = f"{temp_filename} ({(count := count + 1)}){ext}"
                fileinfo["output_file"] = output_filepath
            elif already_exists_mode == "skip" and os.path.isfile(fileinfo["output_file"]):
                logger.info(f"이미 출력파일이 존재합니다... skipped.")
                continue

            fileinfo["state"] = media_compress_encode(
                inputFilepath=fileinfo["input_file"],
                outputFilepath=fileinfo["output_file"],
                isForce=is_force,
                maxHeight=args["height"],
                removeErrorOutput=not is_save_error_output,
                useProgressbar=True,
                leave=False,
            )

            if fileinfo["state"] == FileTaskState.ERROR:
                logger.error(f"미디어를 처리하는 도중, 오류가 발생했습니다. \nState: {fileinfo['state']}\nOutput Filepath: {fileinfo['output_file']}")
            elif (is_skipped := fileinfo["state"] == FileTaskState.SKIPPED) or fileinfo["state"] == FileTaskState.SUCCESS:
                if not is_skipped:
                    if is_replace:
                        try:
                            dest_filepath = f"{os.path.splitext(fileinfo['input_file'])[0]}{ext}"
                            src_filepath = fileinfo["output_file"]
                            fileinfo["output_file"] = dest_filepath

                            shutil.move(src_filepath, dest_filepath)

                            if os.path.splitext(fileinfo["input_file"])[1] != os.path.splitext(fileinfo["output_file"])[1]:
                                os.remove(fileinfo["input_file"])

                            logger.info(f"덮어쓰기 완료: {fileinfo['output_file']}")
                        except Exception as ex:
                            logger.error(f"원본 파일 덮어쓰기 실패: \n{ex}")

                    fileinfo["output_md5_hash"] = utils.get_MD5_hash(fileinfo["output_file"])

                    logger.info(f"작업 완료: \nState: {fileinfo['state']}\nOutput Filepath: {fileinfo['output_file']}\nOutput File MD5 Hash: {fileinfo['output_md5_hash']}")

            logger.debug(f"처리완료 최종 파일 정보: \n{pformat(fileinfo)}")


if __name__ == "__main__":
    main()
