import os
import warnings

import bitmath
from tqdm import TqdmWarning, tqdm

from py_media_compressor import encoder, log, model, utils
from py_media_compressor.const import FILE_EXT_FILTER_LIST
from py_media_compressor.encoder import args_builder
from py_media_compressor.model.enum import FileTaskStatus, LogLevel
from py_media_compressor.utils import pformat

# 경고 문구 무시
warnings.filterwarnings(action="ignore", category=TqdmWarning)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="미디어를 압축 인코딩합니다.")

    parser.add_argument(
        "-i",
        dest="input",
        action="append",
        required=True,
        help="하나 이상의 입력 소스 파일 및 디렉토리 경로 또는, .list 파일(파일의 경로 모음, 줄바꿈으로 구분) 경로",
    )
    parser.add_argument("-o", dest="output", default="out", help="출력 디렉토리 경로")
    parser.add_argument(
        "-r",
        "--replace",
        dest="replace",
        action="store_true",
        help="원본 파일보다 작을 경우, 원본 파일을 덮어씁니다. 아닐 경우, 출력파일이 삭제됩니다.",
    )
    parser.add_argument(
        "-p",
        "--size_skip",
        dest="size_skip",
        action="store_true",
        help="빠른 작업을 위해 인코딩 도중 출력파일 크기가 입력파일 크기보다 커지는 순간 즉시 건너뜁니다.",
    )
    parser.add_argument(
        "-e",
        "--already_exists_mode",
        dest="already_exists_mode",
        choices=["overwrite", "skip", "numbering"],
        default="numbering",
        help="출력 폴더에 같은 이름의 파일이 있을 경우, 사용할 모드.",
    )
    # parser.add_argument(
    #     "--no_sort", dest="sort", action="store_false", help="파일크기 오름차순으로 정렬을 하지 않습니다."
    # )
    parser.add_argument(
        "--sort_mode",
        dest="sort_mode",
        choices=["on", "reverse", "off"],
        default="on",
        help="파일 사이즈 정렬 옵션 (on = 내림차순, reverse = 오름차순)",
    )
    parser.add_argument(
        "-s",
        "--save_error_output",
        dest="save_error_output",
        action="store_true",
        help="오류가 발생한 출력물을 제거하지 않습니다.",
    )
    parser.add_argument("-f", "--force", dest="force", action="store_true", help="이미 압축된 미디어 파일을 강제로, 재압축합니다.")
    parser.add_argument(
        "-c",
        "--codec",
        dest="codec",
        choices=["h.264", "h.265"],
        default="h.264",
        help="인코더에 전달되는 비디오 코덱 옵션",
    )
    parser.add_argument(
        "--crf",
        dest="crf",
        choices=range(-1, 52),
        default=-1,
        metavar="{-1~51}",
        help="인코더에 전달되는 crf 값 (-1을 입력하면 코덱에 따라 기본값이 자동으로 계산됩니다.) [h.264 = 23, h.265 = 28]",
    )
    parser.add_argument(
        "--scan",
        dest="scan",
        action="store_true",
        help="해당 옵션을 사용하면, 입력 파일을 탐색하고, 실제 압축은 하지 않습니다.",
    )
    parser.add_argument(
        "--height",
        dest="height",
        default=1440,
        help="출력 비디오 스트림의 최대 세로 픽셀 수를 설정합니다. (가로 픽셀 수는 비율에 맞게 자동으로 계산됨)",
    )
    parser.add_argument("--cuda", dest="cuda", action="store_true", help="CUDA 그래픽카드를 사용하여 소스 파일을 디코드합니다.")
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=[ll.name.lower() for ll in LogLevel if ll.name != "DEFAULT"],
        default="info",
        help="로그 레벨 설정",
    )
    parser.add_argument(
        "--log-mode",
        dest="log_mode",
        choices=["c", "f", "cf", "console", "file", "consolefile"],
        default="consolefile",
        help="로그 출력 모드",
    )
    parser.add_argument("--log-path", dest="log_path", default=log.SETTINGS["dir"], help="로그 출력 경로")

    args = vars(parser.parse_args())

    log.SETTINGS["level"] = LogLevel[args["log_level"].upper()]
    log.SETTINGS["use_console"] = args["log_mode"] in ["c", "cf", "console", "consolefile"]
    log.SETTINGS["use_rotatingfile"] = args["log_mode"] in ["f", "cf", "file", "consolefile"]

    if not utils.is_str_empty_or_space(args["log_path"]):
        log.SETTINGS["dir"] = args["log_path"]

    logger = log.get_logger(main)

    logger.info("** 프로그램 시작점 **")
    logger.debug(f"입력 인수\n{pformat(args)}")

    for info in (
        utils.check_command_availability("ffmpeg -version"),
        utils.check_command_availability("ffprobe -version"),
    ):
        if not info[0] or logger.isEnabledFor(LogLevel.DEBUG):
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

        if logger.isEnabledFor(LogLevel.DEBUG):
            logger.debug(f"command 실행 가능 여부, 검사 정보: {info_str}")

    logger.debug("ffmpeg, ffprobe 동작 확인 완료")

    # 확장자 필터 로드
    ext_filter_config_filepath = os.path.join("config", "filter.yaml")
    if os.path.isfile(ext_filter_config_filepath):
        ext_filter = utils.load_config(ext_filter_config_filepath)
    else:
        ext_filter = {"exts": FILE_EXT_FILTER_LIST}
        utils.save_config(ext_filter, ext_filter_config_filepath)

    logger.info("파일 확장자 필터 로드 완료")

    # 입력 소스 파일 추출 및 중복 제거
    source_infos, file_count, dupl_file_count = encoder.get_source_file(
        args["input"], ext_filter.get("exts"), useProgressbar=True
    )
    file_infos = encoder.convert_SI2FI(source_infos)

    if args["scan"]:
        logger.info(f"입력 소스파일: \n{pformat(file_infos)}")
    elif logger.isEnabledFor(LogLevel.DEBUG):
        logger.debug(f"입력 소스파일: \n{pformat(file_infos)}")

    logger.info(f"감지된 소스파일 수: {dupl_file_count + file_count}, 입력 소스파일 수: {file_count}, 중복 소스파일 수: {dupl_file_count}")

    if args["scan"]:
        return

    output_dirpath = args["output"]
    logger.info(f"출력 디렉토리: {output_dirpath}")
    os.makedirs(output_dirpath, exist_ok=True)

    is_save_error_output = args["save_error_output"]
    already_exists_mode = args["already_exists_mode"]
    try:
        max_height = int(args["height"])
        assert max_height > 0
    except Exception:
        max_height = 1440

    if logger.isEnabledFor(LogLevel.DEBUG):
        logger.debug(f"현재 작업 소스 정보: \n{pformat(file_infos)}")

    encode_option = model.EncodeOption(
        maxHeight=max_height,
        isForce=args["force"],
        codec=args["codec"],
        crf=args["crf"],
        removeErrorOutput=not is_save_error_output,
        useProgressbar=True,
        leave=False,
        isCuda=args["cuda"],
        isReplace=args["replace"],
        isSizeSkip=args["size_skip"],
    )

    sort_mode = args.get("sort_mode", "on").lower()
    if sort_mode == "on":
        file_infos.sort(key=lambda fi: fi.input_filesize)
    elif sort_mode == "reverse":
        file_infos.sort(key=lambda fi: fi.input_filesize, reverse=True)

    ffmpeg_args: model.FFmpegArgs
    for file_info in (file_info_tqdm := tqdm(file_infos, leave=False, dynamic_ncols=True)):
        file_info_tqdm.set_description(f"Processing... {os.path.basename(file_info.input_filepath)}")

        # tqdm 소스 파일 크기 표시
        input_file_size_h = str(bitmath.best_prefix(int(file_info.input_filesize), system=bitmath.SI)).split(" ")
        input_file_size_h = f"{round(float(input_file_size_h[0]), 1)} {input_file_size_h[1]}"
        file_info_tqdm.set_postfix(size=input_file_size_h)

        try:
            ffmpeg_args = model.FFmpegArgs(fileInfo=file_info, encodeOption=encode_option.clone())
        except Exception:
            logger.error(
                f"파일 정보를 불러오는 도중 오류가 발생했습니다. Skipped.\nFileInfo: {pformat(file_info)}",
                exc_info=True,
            )
            continue

        try:
            ext = ffmpeg_args.expected_ext
        except Exception:
            logger.error(f"출력 파일 확장자를 추정할 수 없습니다. Skipped.\nFFmpegArgs: {pformat(ffmpeg_args)}", exc_info=True)
            continue

        ffmpeg_args.file_info.output_filepath = os.path.join(
            output_dirpath, f"{os.path.splitext(os.path.basename(ffmpeg_args.file_info.input_filepath))[0]}{ext}"
        )

        if already_exists_mode == "numbering":
            count = 0
            output_filepath = ffmpeg_args.file_info.output_filepath
            temp_filename = os.path.splitext(output_filepath)[0]
            while os.path.isfile(output_filepath):
                output_filepath = f"{temp_filename} ({(count := count + 1)}){ext}"
            ffmpeg_args.file_info.output_filepath = output_filepath
        elif already_exists_mode == "skip" and os.path.isfile(ffmpeg_args.file_info.output_filepath):
            logger.info("이미 출력파일이 존재합니다... skipped.")
            continue

        is_replace = ffmpeg_args.encode_option.is_replace

        try:
            file_info = encoder.media_compress_encode(ffmpeg_args)
        except Exception:
            logger.error(f"처리하지 않은 오류가 발생하였습니다.\nArgs: {pformat(ffmpeg_args.as_dict())}")
            raise

        del ffmpeg_args

        def replace_input_output(fileInfo: model.FileInfo):
            dest_filepath = os.path.splitext(fileInfo.input_filepath)[0] + os.path.splitext(fileInfo.output_filepath)[1]
            src_filepath = fileInfo.output_filepath

            is_removed = False
            if (  # 파일 시스템이 대소문자를 구분하지 않을 경우
                os.path.basename(fileInfo.input_filepath).lower() == os.path.basename(fileInfo.output_filepath).lower()
            ) and os.path.isfile(fileInfo.input_filepath):
                is_removed = True
                utils.remove(fileInfo.input_filepath)

            utils.move(src_filepath, dest_filepath)
            fileInfo.output_filepath = dest_filepath

            utils.set_file_permission(fileInfo.output_filepath)

            if (
                not is_removed
                and os.path.basename(fileInfo.input_filepath) != os.path.basename(fileInfo.output_filepath)
                and os.path.isfile(fileInfo.input_filepath)
            ):
                utils.remove(fileInfo.input_filepath)

            logger.info("덮어쓰기 성공")

        def streamcopy(fileInfo: model.FileInfo):
            logger.info("스트림 복사 및 메타데이터를 삽입합니다.")
            fileInfo.status = FileTaskStatus.INIT
            ffmpeg_args = model.FFmpegArgs(fileInfo=fileInfo, encodeOption=encode_option.clone())
            args_builder.add_stream_copy_args(ffmpegArgs=ffmpeg_args)
            args_builder.add_metadata_args(ffmpegArgs=ffmpeg_args)
            fileInfo = encoder.media_compress_encode(ffmpegArgs=ffmpeg_args)
            replace_input_output(fileInfo=fileInfo)
            fileInfo.output_filepath = fileInfo.input_filepath

        if file_info.status == FileTaskStatus.ERROR:
            logger.error(
                f"미디어를 처리하는 도중, 오류가 발생했습니다.\nState: {file_info.status}\nInput Filepath: {file_info.input_filepath}\nOutput Filepath: {file_info.output_filepath}"
            )
        elif (is_skipped := file_info.status == FileTaskStatus.SKIPPED) or file_info.status == FileTaskStatus.SUCCESS:
            if not is_skipped:
                if is_replace:
                    try:
                        if (
                            file_info.input_filesize > file_info.output_filesize
                            or os.path.splitext(file_info.input_filepath)[1].lower()
                            != os.path.splitext(file_info.output_filepath)[1].lower()
                        ):
                            replace_input_output(fileInfo=file_info)
                        else:
                            logger.warning(f"덮어쓰기 조건을 만족하지 못합니다. 출력파일을 삭제합니다.\nFileInfo: {file_info}")
                            utils.remove(file_info.output_filepath)

                            streamcopy(fileInfo=file_info)
                    except Exception:
                        logger.error("Replace 작업 실패", exc_info=True)
        elif file_info.status == FileTaskStatus.SUSPEND:
            logger.warning(
                f"사용자에 의해 모든 작업이 중단됨.\nState: {file_info.status}\nInput Filepath: {file_info.input_filepath}\nOutput Filepath: {file_info.output_filepath}"
            )
            break
        elif file_info.status == FileTaskStatus.PASS:
            logger.warning(
                f"작업이 통과되었습니다.\nState: {file_info.status}\nInput Filepath: {file_info.input_filepath}\nOutput Filepath: {file_info.output_filepath}"
            )
            utils.remove(file_info.output_filepath, raise_error=False)
            if is_replace:
                streamcopy(fileInfo=file_info)
        else:
            logger.error(f"상태가 올바르지 않은 작업이 있습니다.\nFileInfo: {file_info}")

        logger.info(f"처리완료\n최종 파일 정보: {pformat(file_info)}")


if __name__ == "__main__":
    main()
