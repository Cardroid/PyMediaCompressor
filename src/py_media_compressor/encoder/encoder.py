import os
import queue
from threading import Thread
from typing import Any, Dict, List, Tuple
import bitmath
import ffmpeg
from tqdm import tqdm

from py_media_compressor import log, utils
from py_media_compressor.common import progress
from py_media_compressor.const import STREAM_FILTER
from py_media_compressor.encoder import add_auto_args
from py_media_compressor.model import FileInfo, FFmpegArgs
from py_media_compressor.model.enum import FileTaskStatus, LogLevel
from py_media_compressor.utils import pformat


def media_compress_encode(ffmpegArgs: FFmpegArgs) -> FileInfo:
    """미디어를 압축합니다.

    Args:
        ffmpegArgs (FFmpegArgs): 인코더, 파일 소스를 포함한 인자

    Returns:
        FileInfo: 파일 정보
    """

    logger = log.get_logger(media_compress_encode)

    if ffmpegArgs.file_info.status == FileTaskStatus.INIT:
        add_auto_args(ffmpegArgs=ffmpegArgs)
        logger.debug("ffmpeg 인자 자동 생성 완료")

    if logger.isEnabledFor(LogLevel.INFO):
        logger.info(f"현재 작업 파일 정보: \n{pformat(ffmpegArgs.get_all_in_one_dict())}")

    if ffmpegArgs.file_info.status == FileTaskStatus.SKIPPED:
        return ffmpegArgs.file_info

    ffmpeg_args_dict = ffmpegArgs.as_dict()

    stream = ffmpeg.input(ffmpegArgs.file_info.input_filepath)

    streams = []
    for stm in ffmpegArgs.probe_info["streams"]:
        if stm["codec_name"] not in STREAM_FILTER:
            streams.append(stream[str(stm["index"])])

    stream = ffmpeg.output(*streams, **ffmpeg_args_dict)

    stream = ffmpeg._ffmpeg.global_args(stream, "-hide_banner")

    stream = ffmpeg.overwrite_output(stream)

    def msg_reader(queue: queue.Queue, temp_msg_storage: List = None):
        total_duration = float(ffmpegArgs.probe_info["format"]["duration"])
        bar = tqdm(total=round(total_duration, 2), leave=ffmpegArgs.encode_option.leave, dynamic_ncols=True)
        info = {}

        for msg in iter(queue.get, None):
            if msg["type"] == "stderr":
                if logger.isEnabledFor(LogLevel.DEBUG):
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

    def error_output_check(ffmpegArgs: FFmpegArgs):
        if ffmpegArgs.encode_option.remove_error_output and ffmpegArgs.file_info.status == FileTaskStatus.ERROR and os.path.isfile(ffmpegArgs.file_info.output_filepath):
            os.remove(ffmpegArgs.file_info.output_filepath)
            logger.info(f"오류가 발생한 출력파일을 제거했습니다. Path: {ffmpegArgs.file_info.output_filepath}")
        return ffmpegArgs.file_info

    logger.info(f"ffmpeg Arguments: \n[ffmpeg {' '.join(ffmpeg.get_args(stream))}]")

    if ffmpegArgs.encode_option.use_progressbar:
        msg_queue = queue.Queue()
        temp_msg_storage = []
        try:
            process = progress.run_ffmpeg_process_with_msg_queue(stream, msg_queue)
            utils.set_low_process_priority(process.pid)

            Thread(target=msg_reader, args=[msg_queue, temp_msg_storage]).start()

            if process.wait() != 0:
                raise Exception("프로세스가 올바르게 종료되지 않았습니다.")

            utils.set_file_permission(ffmpegArgs.file_info.output_filepath)
            ffmpegArgs.file_info.status = FileTaskStatus.SUCCESS
            return ffmpegArgs.file_info

        except Exception as err:
            ffmpegArgs.file_info.status = FileTaskStatus.ERROR
            logger.error(f"미디어 처리 오류: \n{pformat(temp_msg_storage)}\n{err}")
            utils.set_file_permission(ffmpegArgs.file_info.output_filepath)
            return error_output_check(ffmpegArgs)
    else:
        try:
            process = ffmpeg.run_async(stream_spec=stream, pipe_stdout=True, pipe_stderr=True)
            _, stderr = process.communicate()
            utils.set_low_process_priority(process.pid)

            if process.poll() != 0:
                raise ffmpeg.Error("ffmpeg", "", stderr)

            logger.info(utils.string_decode(stderr))
            utils.set_file_permission(ffmpegArgs.file_info.output_filepath)
            ffmpegArgs.file_info.status = FileTaskStatus.SUCCESS
            return ffmpegArgs.file_info

        except ffmpeg.Error as err:
            ffmpegArgs.file_info.status = FileTaskStatus.ERROR
            logger.error(utils.string_decode(err.stderr))
            utils.set_file_permission(ffmpegArgs.file_info.output_filepath)
            return error_output_check(ffmpegArgs)


def get_source_file(inputPaths: List[str], mediaExtFilter: List[str] = None, useProgressbar=False, leave=True) -> Tuple[List, int, int]:
    """입력 경로에서 소스파일을 검색합니다.

    Args:
        inputPaths (List[str]): 입력 경로
        mediaExtFilter (List[str], optional): 미디어 확장자 필터. Defaults to None.
        useProgressbar (bool, optional): 진행바 사용 여부. Defaults to False.
        leave (bool, optional): 중첩된 진행바를 사용할 경우, False 를 권장합니다. Defaults to True.

    Returns:
        Tuple[List, int, int]: 검색된 소스 파일 정보 리스트, 검색된 파일 수, 중복 소스 파일 수
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

    input_iter = tqdm(inputPaths, desc="입력 경로에서 파일 검색 중...", leave=leave, dynamic_ncols=True) if useProgressbar else inputPaths
    for input_filepath in input_iter:
        if useProgressbar:
            input_iter.set_postfix(input_filepath=input_filepath)

        input_filepath = os.path.normpath(input_filepath)
        detected_fileinfos = []

        media_files = utils.get_media_files(input_filepath, mediaExtFilter=mediaExtFilter)
        media_files_iter = tqdm(media_files, leave=False, dynamic_ncols=True) if useProgressbar else media_files
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


def convert_SI2FI(source_infos: List[Dict[str, Any]]) -> List[FileInfo]:
    """소스 파일 정보 Dict의 형식을 FileInfo로 변환합니다.

    Args:
        source_infos (List[Dict[str, Any]]): 소스 파일 정보 리스트

    Returns:
        List[FileInfo]: 변환된 FileInfo 리스트
    """

    result = []

    for source_info in [file for source_info in source_infos for file in source_info["files"]]:
        result.append(file_info := FileInfo(source_info["input_file"]))

        data = file_info.as_dict()

        if input_file_size := source_info.get("input_file_size"):
            data["input_filesize"] = input_file_size
        if input_md5_hash := source_info.get("input_md5_hash"):
            data["input_file_MD5"] = input_md5_hash

    return result
