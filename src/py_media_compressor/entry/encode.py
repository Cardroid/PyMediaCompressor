import os
import shutil
from tqdm import tqdm

from py_media_compressor import log, utils
from py_media_compressor.utils import pformat
from py_media_compressor.const import FILE_EXT_FILTER_LIST
from py_media_compressor.encoder.encoder import FileTaskState
from py_media_compressor.encoder import encoder


def main():
    import argparse

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
    parser.add_argument("--scan", dest="scan", action="store_true", help="해당 옵션을 사용하면, 입력 파일을 탐색하고, 실제 압축은 하지 않습니다.")
    parser.add_argument("--height", dest="height", default=1440, help="출력 비디오 스트림의 최대 세로 픽셀 수를 설정합니다.")

    args = vars(parser.parse_args())

    log.SETTINGS["level"] = log.LOGLEVEL_DICT[args["log_level"].lower()]
    log.SETTINGS["use_console"] = args["log_mode"] in ["c", "cf", "console", "consolefile"]
    log.SETTINGS["use_rotatingfile"] = args["log_mode"] in ["f", "cf", "file", "consolefile"]

    if args["log_path"] != "" and not args["log_path"].isspace():
        log.SETTINGS["dir"] = args["log_path"]

    logger = log.get_logger(main)

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
                },
                width=160,
            )

        if not info[0]:
            logger.critical(f"ffmpeg 또는 ffprobe 동작 확인 불가, 해당 프로그램은 ffmpeg 및 ffprobe가 필요합니다.\nInfo: {info_str}")
            return

        if logger.isEnabledFor(log.DEBUG):
            logger.debug(f"command 실행 가능 여부, 검사 정보: {info_str}")

    logger.debug(f"ffmpeg, ffprobe 동작 확인 완료")

    # 확장자 필터 로드
    ext_filter_config_filepath = os.path.join("config", "filter.yaml")
    if os.path.isfile(ext_filter_config_filepath):
        ext_filter = utils.load_config(ext_filter_config_filepath)
    else:
        ext_filter = {"exts": FILE_EXT_FILTER_LIST}
        utils.save_config(ext_filter, ext_filter_config_filepath)

    logger.info(f"파일 확장자 필터 로드 완료")

    # 입력 소스 파일 추출 및 중복 제거
    source_infos, file_count, dupl_file_count = encoder.get_source_file(args["input"], ext_filter.get("exts", None), useProgressbar=True)

    if args["scan"]:
        logger.info(f"입력 소스파일: \n{pformat(source_infos)}")
    else:
        logger.debug(f"입력 소스파일: \n{pformat(source_infos)}")

    logger.info(f"감지된 소스파일 수: {dupl_file_count + file_count}, 입력 소스파일 수: {file_count}, 중복 소스파일 수: {dupl_file_count}")

    if args["scan"]:
        return

    output_dirpath = args["output"]
    logger.info(f"출력 디렉토리: {output_dirpath}")
    os.makedirs(output_dirpath, exist_ok=True)

    log.LogDest = log.LogDestination.FILE

    is_replace = args["replace"]
    is_force = args["force"]
    is_save_error_output = args["save_error_output"]
    already_exists_mode = args["already_exists_mode"]

    logger.debug(f"현재 작업 소스 정보: \n{pformat(source_infos)}")

    for fileinfo in (fileinfo_tqdm := tqdm([file for source_info in source_infos for file in source_info["files"]], leave=False)):
        fileinfo_tqdm.set_postfix(filename=os.path.basename(fileinfo["input_file"]))
        logger.info(f"현재 작업 파일 정보: \n{pformat(fileinfo)}")

        try:
            ext = encoder.get_output_fileext(fileinfo["input_file"])
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

        fileinfo["state"] = encoder.media_compress_encode(
            inputFilepath=fileinfo["input_file"],
            outputFilepath=fileinfo["output_file"],
            isForce=is_force,
            maxHeight=args["height"],
            removeErrorOutput=not is_save_error_output,
            useProgressbar=True,
            leave=False,
        )

        if fileinfo["state"] == FileTaskState.ERROR:
            logger.error(f"미디어를 처리하는 도중, 오류가 발생했습니다. \nState: {fileinfo['state']}\nInput Filepath: {fileinfo['input_file']}\nOutput Filepath: {fileinfo['output_file']}")
        elif (is_skipped := fileinfo["state"] == FileTaskState.SKIPPED) or fileinfo["state"] == FileTaskState.SUCCESS:
            if not is_skipped:
                if is_replace:
                    try:
                        fileinfo["output_file_size"] = os.path.getsize(fileinfo["output_file"])

                        if fileinfo["input_file_size"] > fileinfo["output_file_size"]:
                            dest_filepath = f"{os.path.splitext(fileinfo['input_file'])[0]}{ext}"
                            src_filepath = fileinfo["output_file"]
                            fileinfo["output_file"] = dest_filepath

                            shutil.move(src_filepath, dest_filepath)
                            utils.set_file_permission(dest_filepath)

                            if os.path.splitext(fileinfo["input_file"])[1] != os.path.splitext(fileinfo["output_file"])[1]:
                                os.remove(fileinfo["input_file"])

                            logger.info(f"덮어쓰기 성공")
                        else:
                            logger.info(f"원본 크기가 더 큽니다. 출력파일을 삭제합니다.")
                            os.remove(fileinfo["output_file"])
                            fileinfo["output_file"] = fileinfo["input_file"]
                    except Exception as ex:
                        logger.error(f"원본 파일 덮어쓰기 실패: \n{ex}")

                # fileinfo["output_md5_hash"] = utils.get_MD5_hash(fileinfo["output_file"])

        logger.info(f"처리완료\n최종 파일 정보: {pformat(fileinfo)}")
