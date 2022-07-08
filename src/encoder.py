import os
import ffmpeg
import log
import utils

PROCESSER_NAME = "Automatic media compression processed"


def media_compress_encode(inputFilepath: str, outputDirpath: str, isForce=False, maxHeight=1440):
    """미디어를 압축합니다.

    Args:
        input_filepath (str): 미디어 파일 경로
        output_dirpath (str): 출력 디렉토리 경로
        is_force (bool, optional): 이미 처리된 미디어 파일을 강제적으로 재처리합니다. Defaults to False.
        max_height (int, optional): 미디어의 최대 세로 픽셀. Defaults to 1440.
    """

    probe = ffmpeg.probe(inputFilepath)
    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)

    is_only_audio = video_stream == None

    os.makedirs(outputDirpath, exist_ok=True)

    ffmpeg_global_args = {}

    if is_only_audio:
        format = "ipod"  # == m4a
        ext = "m4a"
    else:
        ffmpeg_global_args["c:v"] = "libx264"
        ffmpeg_global_args["crf"] = 20
        ffmpeg_global_args["preset"] = "veryslow"
        format = "mp4"
        ext = "mp4"
        height = int(video_stream["height"])
        if height > maxHeight:
            ffmpeg_global_args["vf"] = f"scale=-1:{maxHeight}"

    output_filepath = f"{os.path.join(outputDirpath, os.path.splitext(os.path.basename(inputFilepath))[0])}.{ext}"
    ffmpeg_global_args["filename"] = output_filepath
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
            comment = f"{comment}\n{PROCESSER_NAME}"
        ffmpeg_global_args["metadata"] = f'"comment={comment}"'
    else:
        # * 영상이 이미 처리된 경우
        print("INFO: 이미 처리된 미디어입니다.", end="")
        if isForce:
            print(f"\nINFO: 강제로 재인코딩을 실시합니다... is_force: {isForce}")
        else:
            print(".. skip")
            exit(0)

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

    # * DEBUG
    # ffmpeg_global_args["t"] = 10

    stream = ffmpeg.input(inputFilepath)

    stream = ffmpeg.output(stream, **ffmpeg_global_args)

    print(f"ffmpeg {' '.join(ffmpeg.get_args(stream))}")

    stream = ffmpeg.overwrite_output(stream)

    ffmpeg.run(stream)


def main():
    import argparse
    from pprint import pformat

    parser = argparse.ArgumentParser(description="미디어를 압축 인코딩합니다.")

    parser.add_argument("--log-mode", choices=["c", "f", "cf", "console", "file", "consolefile"], dest="log_mode", default="consolefile", help="로그 출력 모드 설정")
    parser.add_argument("--log-level", choices=log.LOGLEVEL_DICT.keys(), dest="log_level", default="info", help="로그 레벨 설정")
    parser.add_argument("-i", dest="input", action="append", required=True, help="하나 이상의 입력 소스 파일 또는 디렉토리 경로")
    parser.add_argument("-o", dest="output", default="out", help="출력 디렉토리 경로")
    parser.add_argument("--view-source", dest="view_source", action="store_true", help="입력된 경로에서 감지된 소스파일 목록")

    args = vars(parser.parse_args())

    logger = log.get_logger(
        name=f"{__name__}.command",
        logLevel=log.LOGLEVEL_DICT[args["log_level"]],
        useConsole=args["log_mode"] in ["c", "cf", "console", "consolefile"],
        useRotatingfile=args["log_mode"] in ["f", "cf", "file", "consolefile"],
    )

    logger.info("** 인코딩 작업 시작 **")
    logger.debug(f"입력 인수: {args}")

    input_files = []
    input_files.extend(*[utils.get_media_files(path) for path in args["input"]])

    if args["view_source"]:
        logger.info("입력 소스파일: \n" + pformat(input_files))
    else:
        logger.info(f"입력 소스파일 수: {len(input_files)}")
