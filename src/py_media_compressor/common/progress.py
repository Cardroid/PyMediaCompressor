#!/usr/bin/env python
# source from https://github.com/kkroening/ffmpeg-python/issues/43

from typing import IO
import ffmpeg
from queue import Queue
from threading import Thread

from py_media_compressor import utils


def reader(pipe: IO[bytes], queue: Queue, pipe_name: str):
    try:
        with pipe:
            for lines in iter(pipe.readline, b""):
                queue.put((pipe_name, lines))
    finally:
        queue.put(None)


def parser(queue: Queue, return_queue: Queue):
    for _ in range(2):
        for pipe_name, line in iter(queue.get, None):
            line = utils.string_decode(line)
            data = {}
            if pipe_name == "stderr":
                data["type"] = "stderr"
                data["msg"] = line
            elif pipe_name == "stdout":
                data["type"] = "stdout"
                line = line.strip()
                parts = line.split("=")
                if len(parts) == 2:
                    data[parts[0]] = parts[1]
            return_queue.put(data)

    return_queue.put(None)


def run_ffmpeg_process_with_msg_queue(ffmpeg_stream, msg_queue: Queue):
    ffmpeg_stream = ffmpeg._ffmpeg.global_args(ffmpeg_stream, "-progress", "pipe:1")

    ffmpeg_process = ffmpeg.run_async(ffmpeg_stream, pipe_stdout=True, pipe_stderr=True)

    q = Queue()
    Thread(target=reader, args=[ffmpeg_process.stdout, q, "stdout"]).start()
    Thread(target=reader, args=[ffmpeg_process.stderr, q, "stderr"]).start()
    Thread(target=parser, args=[q, msg_queue]).start()

    return ffmpeg_process
