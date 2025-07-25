import logging
import os
import queue
from threading import Thread
from typing import Any, Dict, List, Tuple, Union

import bitmath
import ffmpeg
from tqdm import tqdm

from py_media_compressor import log, utils
from py_media_compressor.common import progress
from py_media_compressor.const import IGNORE_STREAM_FILTER
from py_media_compressor.encoder import args_builder
from py_media_compressor.model import FFmpegArgs, FileInfo
from py_media_compressor.model.enum import FileTaskStatus, LogDestination, LogLevel
from py_media_compressor.utils import pformat


def media_compress_encode(ffmpegArgs: FFmpegArgs) -> FileInfo:
    """미디어를 압축합니다.

    Args:
        ffmpegArgs (FFmpegArgs): 인코더, 파일 소스를 포함한 인수

    Returns:
        FileInfo: 파일 정보
    """

    logger = log.get_logger(media_compress_encode)

    if ffmpegArgs.file_info.status == FileTaskStatus.INIT:
        args_builder.add_auto_args(ffmpegArgs=ffmpegArgs)
        logger.debug("ffmpeg 인수 자동 생성 완료")

    if logger.isEnabledFor(LogLevel.INFO):
        logger.info(f"현재 작업 파일 정보: \n{pformat(ffmpegArgs.get_all_in_one_dict())}")

    if ffmpegArgs.file_info.status in [FileTaskStatus.SKIPPED, FileTaskStatus.PASS]:
        return ffmpegArgs.file_info

    if ffmpegArgs.file_info.status != FileTaskStatus.WAITING:
        logger.error("해당 작업의 상태가 올비르지 않습니다. Skipped.")
        return ffmpegArgs.file_info

    ffmpegArgs.file_info.status = FileTaskStatus.PROCESSING

    ffmpeg_args_dict = ffmpegArgs.as_dict()

    input_Args = {}

    if (
        ffmpegArgs.encode_option.is_cuda
        and not ffmpegArgs.is_only_audio
        and not ffmpegArgs.video_stream["codec_name"].lower().startswith("wmv")
    ):  # wmv 코덱 중, 하드웨어 디코드 오류가 발생하는 문제가 있음
        input_Args["hwaccel"] = "cuda"
        logger.info("CUDA 디코더 활성화")

    skip_offset_size = 10485760  # 10 * 1024 * 1024 (10MB)

    is_can_skip = args_builder.pass_filter(ffmpegArgs=ffmpegArgs)

    stream = ffmpeg.input(ffmpegArgs.file_info.input_filepath, **input_Args)

    ignored_streams = []
    streams = []
    for stm in ffmpegArgs.probe_info["streams"]:
        if (
            str(stm.get("codec_type", "")).lower() in ["video", "audio"]
            and str(stm.get("codec_name", "")).lower() not in IGNORE_STREAM_FILTER
        ):
            streams.append(stream[str(stm["index"])])
        else:
            ignored_streams.append(stm)

    if len(ignored_streams) > 0:
        logger.warning(
            f"무시된 스트림이 존재합니다.\nIgnored Streams: {pformat(ignored_streams)}\nFileInfo: {pformat(ffmpegArgs.file_info)}"
        )

    stream = ffmpeg.output(*streams, **ffmpeg_args_dict)

    stream = ffmpeg._ffmpeg.global_args(stream, "-hide_banner")

    stream = ffmpeg.overwrite_output(stream)

    def msg_reader(
        logger: logging.Logger,
        queue: queue.Queue,
        ffmpegArgs: FFmpegArgs,
        control_queue: queue.Queue,
        msg_storage: List = None,
    ):
        file_info = ffmpegArgs.file_info
        total_duration = float(ffmpegArgs.probe_info["format"]["duration"])
        bar = tqdm(total=round(total_duration, 2), leave=ffmpegArgs.encode_option.leave, dynamic_ncols=True)
        info = {
            "spd": "",
            "time": "",
            "size": "",
            "frame": "",
            "fps": "",
            "br": "",
        }

        for msg in iter(queue.get, None):
            if msg["type"] == "stderr":
                if logger.isEnabledFor(LogLevel.DEBUG):
                    logger.debug(f"ffmpeg output str: \n{pformat(msg)}")
                if msg_storage is not None:
                    msg_storage.append(msg["msg"])

            elif msg["type"] == "stdout":
                update_value = None
                try:
                    if "out_time_ms" in msg:
                        time = max(round(float(msg["out_time_ms"]) / 1000000.0, 2), 0)
                        update_value = time - bar.n
                    elif "progress" in msg and msg["progress"] == "end":
                        update_value = bar.total - bar.n
                except ValueError:
                    update_value = None

                for key, value in msg.items():
                    if key in [
                        "frame",
                        "fps",
                        "total_size",
                        "bitrate",
                        "out_time",
                        "speed",
                        "dup_frames",
                        "drop_frames",
                    ]:
                        if key == "total_size":
                            key = "size"
                            f_value = int(value)
                            p_value = str(bitmath.best_prefix(f_value, system=bitmath.SI)).split(" ")
                            value = f"{round(float(p_value[0]), 1)} {p_value[1]}"
                            if (
                                is_can_skip
                                and ffmpegArgs.encode_option.is_size_skip
                                and not ffmpegArgs.is_streamcopy
                                and not ffmpegArgs.is_only_audio
                                and control_queue is not None
                            ):
                                if f_value > file_info.input_filesize + skip_offset_size:
                                    control_queue.put("pass")
                                    logger.info(
                                        (
                                            f"[size_skip] input size > output size. "
                                            f"({f_value} > {file_info.input_filesize})"
                                        )
                                    )
                        elif key == "out_time":
                            key = "time"
                            value = value.split(".")[0]
                        elif key == "bitrate":
                            key = "br"
                        elif key == "speed":
                            key = "spd"
                        elif key == "dup_frames":
                            if value == "0":
                                continue
                            else:
                                key = "dup_f"
                        elif key == "drop_frames":
                            if value == "0":
                                continue
                            else:
                                key = "drop_f"

                        info[key] = value

                if update_value is not None:
                    bar.set_postfix(info, refresh=False)
                    bar.update(update_value)
                else:
                    bar.set_postfix(info)

        bar.close()

    def error_output_check(ffmpegArgs: FFmpegArgs):
        if (
            ffmpegArgs.encode_option.remove_error_output
            and (
                ffmpegArgs.file_info.status == FileTaskStatus.ERROR
                or ffmpegArgs.file_info.status == FileTaskStatus.SUSPEND
            )
            and os.path.isfile(ffmpegArgs.file_info.output_filepath)
        ):
            utils.remove(ffmpegArgs.file_info.output_filepath)
            logger.info(f"완전하지 않은 출력파일을 제거했습니다. Path: {ffmpegArgs.file_info.output_filepath}")
        return ffmpegArgs.file_info

    logger.info(f"ffmpeg Arguments: \n[ffmpeg {' '.join(ffmpeg.get_args(stream))}]")

    try:
        if ffmpegArgs.encode_option.use_progressbar:
            msg_queue = queue.Queue()
            control_queue = queue.Queue()
            msg_storage = []
            process = progress.run_ffmpeg_process_with_msg_queue(stream, msg_queue)
            utils.set_low_process_priority(process.pid)

            watch_thread = Thread(
                target=msg_reader,
                args=[
                    logger,
                    msg_queue,
                    ffmpegArgs,
                    control_queue,
                    msg_storage,
                ],
            )
            watch_thread.start()

            code, result = utils.process_control_wait(process, control_queue=control_queue)

            watch_thread.join()

            if code != 0:
                if result == "suspend":
                    ffmpegArgs.file_info.status = FileTaskStatus.SUSPEND
                    raise RuntimeWarning("사용자 입력에 의해 취소되었습니다.")
                elif result == "pass":
                    ffmpegArgs.file_info.status = FileTaskStatus.PASS
                    raise RuntimeWarning("작업이 통과되었습니다.")
                else:
                    raise Exception("프로세스가 올바르게 종료되지 않았습니다.\nstderr: " + "".join(msg_storage))

        else:
            process = ffmpeg.run_async(stream_spec=stream, pipe_stdout=True, pipe_stderr=True)
            _, stderr = process.communicate()
            utils.set_low_process_priority(process.pid)

            code, result = utils.process_control_wait(process)

            if code != 0:
                if result == "suspend":
                    ffmpegArgs.file_info.status = FileTaskStatus.SUSPEND
                    raise RuntimeWarning("사용자 입력에 의해 취소되었습니다.")
                elif result == "pass":
                    ffmpegArgs.file_info.status = FileTaskStatus.PASS
                    raise RuntimeWarning("작업이 통과되었습니다.")
                else:
                    raise Exception(f"프로세스가 올바르게 종료되지 않았습니다.\nstderr: {utils.string_decode(stderr)}")

            logger.info(utils.string_decode(stderr), {"dest": LogDestination.CONSOLE})

    except Exception:
        if ffmpegArgs.file_info.status == FileTaskStatus.SUSPEND:
            logger.warning("작업이 중단되었습니다.")
        elif ffmpegArgs.file_info.status == FileTaskStatus.PASS:
            logger.warning("작업이 통과되었습니다.")
        else:
            ffmpegArgs.file_info.status = FileTaskStatus.ERROR
            logger.error("미디어 처리 중 예외가 발생했습니다.", exc_info=True)
    else:
        ffmpegArgs.file_info.status = FileTaskStatus.SUCCESS
    finally:
        utils.set_file_permission(ffmpegArgs.file_info.output_filepath)
        return error_output_check(ffmpegArgs)


def get_source_file(
    inputPaths: List[str], mediaExtFilter: Union[List[str], None] = None, useProgressbar=False, leave=True
) -> Tuple[List, int, int]:
    """입력 경로에서 소스파일을 검색합니다.

    Args:
        inputPaths (List[str]): 입력 경로
        mediaExtFilter (Union[List[str], None], optional): 미디어 확장자 필터. Defaults to None.
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

                fileinfo["input_md5_hash"] = utils.get_MD5_hash(fileinfo["input_file"], useProgressbar=True)

                if "input_md5_hash" not in o_fileinfo:
                    o_fileinfo["input_md5_hash"] = utils.get_MD5_hash(o_fileinfo["input_file"], useProgressbar=True)

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

    input_iter = (
        tqdm(inputPaths, desc="입력 경로에서 파일 검색 중...", leave=leave, dynamic_ncols=True) if useProgressbar else inputPaths
    )
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

            if (
                dupl_test_result := duplicate_file_filter(
                    detected_filepath, tqdm_manager=media_files_iter if useProgressbar else None
                )
            )[0]:
                detected_fileinfos.append(dupl_test_result[1])
                file_count += 1
            else:
                logger.warning(
                    f"중복 파일이 제외되었습니다.\nOrigin: {pformat(dupl_test_result[1])}\nTest: {pformat(dupl_test_result[2])}"
                )
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
