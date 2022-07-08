import os
from glob import glob
import hashlib

from typing import List

from const import DEMUXER_FILE_EXT_LIST


def get_media_files(path: str, useRealpath=False, useFilter=False) -> List[str]:
    """경로에 해당하는 미디어 파일 및 폴더 내의 모든 미디어 파일을 가져옵니다.

    Args:
        path (str): 경로

    Returns:
        List[str]: 파일의 목록을 반환합니다.
    """

    if useRealpath:
        path = os.path.realpath(path)

    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        path = os.path.join(path, "**")
        return list(filter(lambda p: os.path.isfile(p) and (not useFilter or os.path.splitext(p)[1] in DEMUXER_FILE_EXT_LIST), glob(path, recursive=True)))
    else:
        return []


def get_MD5_hash(filepath: str) -> str:
    """파일의 MD5 해시값을 구합니다.

    Args:
        filepath (str): 파일 경로

    Returns:
        str: MD5 해시값
    """

    hasher = hashlib.md5()

    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            hasher.update(byte_block)
        return hasher.hexdigest()
