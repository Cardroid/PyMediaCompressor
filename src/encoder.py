from enum import Enum, auto, unique
import os
import ffmpeg
from tqdm import tqdm
import log
import utils

PROCESSER_NAME = "Automatic media compression processed"


@unique
class FileTaskState(Enum):
    INIT = auto()
    WAIT = auto()
    SUCCESS = auto()
    ERROR = auto()

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_


def media_compress_encode(inputFilepath: str, outputFilepath: str, isForce=False, maxHeight=1440) -> bool:
    """미디어를 압축합니다.

    Args:
        input_filepath (str): 미디어 파일 경로
        output_dirpath (str): 출력 파일 경로
        is_force (bool, optional): 이미 처리된 미디어 파일을 강제적으로 재처리합니다. Defaults to False.
        max_height (int, optional): 미디어의 최대 세로 픽셀. Defaults to 1440.

    Returns:
        bool: 성공여부
    """

    logger = log.get_logger(name=f"{os.path.splitext(os.path.basename(__file__))[0]}.main")

    if not os.path.isfile(inputFilepath):
        logger.error(f"입력 파일이 존재하지 않습니다. Filepath: {inputFilepath}")
        return False

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
            ffmpeg_global_args["vf"] = f"scale=-1:{maxHeight}"

    # output_filepath = f"{os.path.join(output_dirpath, os.path.splitext(os.path.basename(inputFilepath))[0])}.{ext}"
    # ffmpeg_global_args["filename"] = output_filepath
    ffmpeg_global_args["filename"] = f"{os.path.splitext(outputFilepath)[0]}{ext}"
    ffmpeg_global_args["format"] = format

    # * 영상 메타데이터에 표식 추가
    tags = probe["format"]["tags"]
    comment = ""

    for c in (tags.get("comment", ""), tags.get("COMMENT", "")):
        if c != "" or not c.isspace():
            comment = c
            break

    comment_lines = comment.splitlines(keepends=False)

    if len(comment_lines) == 0 or comment_lines[-1] != PROCESSER_NAME:
        if comment == "":
            comment = PROCESSER_NAME
        else:
            comment = f"{comment}\\n{PROCESSER_NAME}"
        ffmpeg_global_args["metadata"] = f'"comment={comment}"'
    else:
        # TODO: 로깅 모듈 통합 필요
        # * 영상이 이미 처리된 경우
        print("INFO: 이미 처리된 미디어입니다.", end="")
        if isForce:
            print(f"\nINFO: 강제로 재인코딩을 실시합니다... is_force: {isForce}")
        else:
            print(".. skip")
            return

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

    logger.debug(f"ffmpeg {' '.join(ffmpeg.get_args(stream))}")

    stream = ffmpeg.overwrite_output(stream)

    try:
        _, stderr = ffmpeg.run(cmd="ffmpeg", stream_spec=stream, capture_stderr=True)
        logger.info(utils.string_decode(stderr))
    except ffmpeg.Error as err:
        logger.error(utils.string_decode(err.stderr))

    return True


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
    parser.add_argument("-y", "--overwrite", dest="overwrite", action="store_true", help="출력 폴더에 같은 이름의 파일이 있을 경우, 덮어씁니다.")

    args = vars(parser.parse_args())

    log.SETTINGS["level"] = log.LOGLEVEL_DICT[args["log_level"].lower()]
    log.SETTINGS["use_console"] = args["log_mode"] in ["c", "cf", "console", "consolefile"]
    log.SETTINGS["use_rotatingfile"] = args["log_mode"] in ["f", "cf", "file", "consolefile"]

    if args["log_path"] != "" and not args["log_path"].isspace():
        log.SETTINGS["dir"] = args["log_path"]

    logger = log.get_logger(name=f"{os.path.splitext(os.path.basename(__file__))[0]}.main")

    logger.info("** 프로그램 시작점 **")
    logger.debug(f"입력 인수: {args}")

    if (ffmpeginfo := utils.check_command_availability("ffmpeg -version"))[0] and (ffprobeinfo := utils.check_command_availability("ffprobe -version"))[0]:
        if logger.isEnabledFor(log.DEBUG):
            ffmpeginfo_str = pformat(
                {
                    "exit_success": ffmpeginfo[0],
                    "stdout": utils.string_decode(ffmpeginfo[1]).splitlines(),
                    "stderr": utils.string_decode(ffmpeginfo[2]).splitlines(),
                }
            )
            ffprobeinfo_str = pformat(
                {
                    "exit_success": ffprobeinfo[0],
                    "stdout": utils.string_decode(ffprobeinfo[1]).splitlines(),
                    "stderr": utils.string_decode(ffprobeinfo[2]).splitlines(),
                }
            )
            logger.debug(f"ffmpeg, ffprobe 동작 확인 완료\nffmpeg 정보: {ffmpeginfo_str}\nffprobe 정보: {ffprobeinfo_str}", {"dest": log.LogDestination.FILE})
    else:
        logger.critical("ffmpeg 또는 ffprobe 동작 확인 불가, 해당 프로그램은 ffmpeg 및 ffprobe가 필요합니다.")
        return

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
    is_overwrite = args["overwrite"]

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

            if not is_overwrite:
                count = 0
                output_filepath = fileinfo["output_file"]
                temp_filename = os.path.splitext(output_filepath)[0]
                while os.path.isfile(output_filepath):
                    output_filepath = f"{temp_filename} ({(count := count + 1)}){ext}"
                fileinfo["output_file"] = output_filepath

            media_compress_encode(inputFilepath=fileinfo["input_file"], outputFilepath=fileinfo["output_file"])

            if not os.path.isfile(fileinfo["output_file"]):
                fileinfo["state"] = FileTaskState.ERROR
                logger.error(f"압축 처리를 완료했지만, 출력파일이 존재하지 않습니다. \nOutput Filepath: {fileinfo['output_file']}")
            else:
                fileinfo["state"] = FileTaskState.SUCCESS
                fileinfo["output_md5_hash"] = utils.get_MD5_hash(fileinfo["output_file"])

                logger.info(f"압축 처리 완료: \nOutput Filepath: {fileinfo['output_file']}\nOutput File MD5 Hash: {fileinfo['output_md5_hash']}")

                if is_replace:
                    os.replace(fileinfo["output_file"], output_filepath := f"{os.path.splitext(fileinfo['input_file'])[0]}{ext}")

                    if os.path.splitext(fileinfo["input_file"])[1] != os.path.splitext(fileinfo["output_file"])[1]:
                        os.remove(fileinfo["input_file"])

                    fileinfo["output_file"] = output_filepath
                    logger.info(f"덮어쓰기 완료: {fileinfo['output_file']}")

            logger.debug(f"처리완료 최종 파일 정보: \n{pformat(fileinfo)}")


if __name__ == "__main__":
    main()
