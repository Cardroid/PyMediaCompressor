import os
import sys
import ffmpeg


PROCESSER_NAME = "Automatic media compression processed"


def compress_media(input_filepath, output_dirpath, is_force=False, max_height=1440):
    probe = ffmpeg.probe(input_filepath)
    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)

    is_only_audio = video_stream == None

    os.makedirs(output_dirpath, exist_ok=True)

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
        if height > max_height:
            ffmpeg_global_args["vf"] = f"scale=-1:{max_height}"

    output_filepath = f"{os.path.join(output_dirpath, os.path.splitext(os.path.basename(input_filepath))[0])}.{ext}"
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
        if is_force:
            print(f"\nINFO: 강제로 재인코딩을 실시합니다... is_force: {is_force}")
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

    stream = ffmpeg.input(input_filepath)

    stream = ffmpeg.output(stream, **ffmpeg_global_args)

    print(f"ffmpeg {' '.join(ffmpeg.get_args(stream))}")

    stream = ffmpeg.overwrite_output(stream)

    ffmpeg.run(stream)
