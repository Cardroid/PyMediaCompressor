import math
import os
from time import time

from py_media_compressor import log, utils, version
from py_media_compressor.const import PROCESSER_NAME, PROCESSER_TAG_END
from py_media_compressor.model import FFmpegArgs
from py_media_compressor.model.enum import FileTaskStatus, LogLevel

_is_libfdk_aac_enabled = None


def _status_changer(func):
    def wrapper_function(**kwargs):
        result = func(**kwargs)

        if (ffmpegArgs := kwargs.get("ffmpegArgs")) is not None and ffmpegArgs.file_info.status == FileTaskStatus.INIT:
            ffmpegArgs.file_info.status = FileTaskStatus.WAITING

        return result

    return wrapper_function


@_status_changer
def add_auto_args(ffmpegArgs: FFmpegArgs):
    """FFmpeg 인수 자동 추가"""

    add_format_args(ffmpegArgs=ffmpegArgs)
    add_video_args(ffmpegArgs=ffmpegArgs)
    add_audio_args(ffmpegArgs=ffmpegArgs)
    add_metadata_args(ffmpegArgs=ffmpegArgs)


@_status_changer
def add_stream_copy_args(ffmpegArgs: FFmpegArgs):
    """FFmpeg 스트림 복사 인수 추가"""

    ffmpegArgs["c:v"] = "copy"
    ffmpegArgs["c:a"] = "copy"


@_status_changer
def add_format_args(ffmpegArgs: FFmpegArgs):
    """포멧 인수 추가"""

    logger = log.get_logger(add_format_args)

    if ffmpegArgs.is_only_audio:
        format = "ipod"  # == m4a
        ext = ".m4a"
    else:
        format = "mp4"
        ext = ".mp4"

    ffmpegArgs["filename"] = f"{os.path.splitext(ffmpegArgs.file_info.output_filepath)[0]}{ext}"
    ffmpegArgs["format"] = format

    if logger.isEnabledFor(LogLevel.DEBUG):
        logger.debug(f"포멧 인수 추가\nArgs: {ffmpegArgs}\nFileInfo: {ffmpegArgs.file_info}")


@_status_changer
def add_video_args(ffmpegArgs: FFmpegArgs):
    """비디오 인수 추가"""

    logger = log.get_logger(add_video_args)

    if not ffmpegArgs.is_only_audio:
        compression_mode = ffmpegArgs.encode_option.codec
        if compression_mode == "h.264":
            ffmpegArgs["c:v"] = "libx264"
        elif compression_mode == "h.265":
            ffmpegArgs["c:v"] = "libx265"
        ffmpegArgs["crf"] = ffmpegArgs.encode_option.crf
        ffmpegArgs["preset"] = "veryslow"

        # 세로 또는 가로 픽셀 수가 짝수가 아닐 경우 발생하는 오류 처리 포함
        if (width := ffmpegArgs.video_stream.get("width")) is None:
            width = ffmpegArgs.video_stream.get("coded_width")
        if (height := ffmpegArgs.video_stream.get("height")) is None:
            height = ffmpegArgs.video_stream.get("coded_height")

        if height > (max_height := ffmpegArgs.encode_option.max_height):
            width_calc = int(width) * max_height / height

            # round 함수의 기능을 사사오입 법칙을 제외하고 직접 구현
            if width_calc - (width_calc := math.floor(width_calc)) >= 0.5:
                width_calc += 1

            is_even = width_calc % 2 == 0
            ffmpegArgs["vf"] = f"scale={'-1' if is_even else '-2'}:{max_height}"
        else:
            is_wd2 = width % 2 == 1
            is_hd2 = height % 2 == 1

            if is_wd2:
                width += 1
            if is_hd2:
                height += 1

            ffmpegArgs["vf"] = f"scale={width}:{height}"

    if logger.isEnabledFor(LogLevel.DEBUG):
        logger.debug(f"비디오 인수 추가\nArgs: {ffmpegArgs}\nFileInfo: {ffmpegArgs.file_info}")


@_status_changer
def add_audio_args(ffmpegArgs: FFmpegArgs):
    """오디오 인수 추가"""

    logger = log.get_logger(add_audio_args)

    # libfdk_aac 사용 가능할 경우, libfdk_aac 사용
    global _is_libfdk_aac_enabled

    if _is_libfdk_aac_enabled is None:
        _, stdout, _, _ = utils.check_command_availability("ffmpeg -hide_banner -h encoder=libfdk_aac")
        _is_libfdk_aac_enabled = stdout.startswith("Encoder libfdk_aac [Fraunhofer FDK AAC]")

    for idx, audio_stream_info in enumerate(ffmpegArgs.audio_streams):
        if (
            (bit_rate := audio_stream_info.get("bit_rate")) is not None
            and 0 < int(bit_rate) < 512_000
            and audio_stream_info["codec_name"] in ["aac", "mp3"]
        ):
            ffmpegArgs[f"c:a:{idx}"] = "copy"
        else:
            ffmpegArgs[f"c:a:{idx}"] = "libfdk_aac" if _is_libfdk_aac_enabled else "aac"
            ffmpegArgs["cutoff"] = 20000
            ffmpegArgs[f"b:a:{idx}"] = 320_000 if bit_rate is None or int(bit_rate) > 320_000 else int(bit_rate)

    if logger.isEnabledFor(LogLevel.DEBUG):
        logger.debug(f"오디오 인수 추가\nArgs: {ffmpegArgs}\nFileInfo: {ffmpegArgs.file_info}")


@_status_changer
def add_metadata_args(ffmpegArgs: FFmpegArgs):
    """메타데이터 인수 추가"""

    logger = log.get_logger(add_metadata_args)

    if "format" in ffmpegArgs.probe_info and (tags := ffmpegArgs.probe_info["format"].get("tags")) is not None:
        _tags = tags
        tags = {}
        for key, value in _tags.items():
            tags[key.lower()] = value
        del _tags
    else:
        tags = {}

    is_ver_tag_exist = False

    start_idx = -1
    end_idx = -1
    metadata_lines = []
    comment_lines = []
    if not utils.is_str_empty_or_space(comment := tags.get("comment", "")):
        comment_lines = comment.splitlines(keepends=False)
        for idx, c in enumerate(comment_lines):
            if c.startswith(PROCESSER_NAME):
                start_idx = idx
                is_ver_tag_exist = True
            elif c.startswith(PROCESSER_TAG_END):
                end_idx = idx
                break
        if is_ver_tag_exist:
            if end_idx > 0:
                metadata_lines = comment_lines[start_idx + 1 : end_idx]
                comment_lines = comment_lines[:start_idx] + comment_lines[end_idx + 1 :]
            else:
                comment_lines = comment_lines[:start_idx]

    metadatas = {}
    if is_ver_tag_exist:
        for line in metadata_lines:
            key, value = line.split("=")
            metadatas[key.strip().lower()] = value.strip()
    else:
        metadatas["amcp_ver"] = version.metadata_version
        metadatas["amcp_input_filesize"] = ffmpegArgs.file_info.input_filesize
        metadatas["amcp_input_file_MD5"] = ffmpegArgs.file_info.input_file_MD5
        metadatas["amcp_encoded_date"] = int(time())

    if len(metadatas) > 0:
        c_metadata = []
        for k, v in metadatas.items():
            c_metadata.append(f"{k}={v}")

        if len(comment_lines) > 0:
            comment = "\n".join(comment_lines)
        else:
            comment = ""

        if not utils.is_str_empty_or_space(comment):
            comment += "\n"

        if len(c_metadata) > 0:
            comment += f"{PROCESSER_NAME}\n" + "\n".join(c_metadata) + f"\n{PROCESSER_TAG_END}"
        else:
            comment = PROCESSER_NAME

        ffmpegArgs["metadata"] = f"comment={comment}"

    if is_ver_tag_exist:
        # * 영상이 이미 처리된 경우
        logger.info(f"이미 처리된 미디어입니다.\nFileInfo: {ffmpegArgs.file_info}")
        if ffmpegArgs.encode_option.is_force:
            logger.warning("강제로 재인코딩을 실시합니다... (is_force)")
        else:
            ffmpegArgs.file_info.status = FileTaskStatus.SKIPPED

    if logger.isEnabledFor(LogLevel.DEBUG):
        logger.debug(f"메타데이터 인수 추가\nArgs: {ffmpegArgs}\nMetadatas: {utils.pformat(metadatas)}")
