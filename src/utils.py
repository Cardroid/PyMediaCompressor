import os
from glob import glob
import hashlib

from typing import List

from const import DEMUXER_FILE_EXT_LIST


def get_media_files(path: str, useRealpath=False, useMediaExtFilter=False) -> List[str]:
    """경로에 해당하는 미디어 파일 및 폴더 내의 모든 미디어 파일을 가져옵니다.

    Args:
        path (str): 경로
        useRealpath (bool, optional): 절대 경로를 사용합니다. Defaults to False.
        useMediaExtFilter (bool, optional): ffmpeg에서 디먹싱 가능한 확장자 목록으로 필터링합니다. Defaults to False.

    Returns:
        List[str]: 파일의 목록을 반환합니다.
    """

    if useRealpath:
        path = os.path.realpath(path)

    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        path = os.path.join(path, "**")
        return list(filter(lambda p: os.path.isfile(p) and (not useMediaExtFilter or os.path.splitext(p)[1] in DEMUXER_FILE_EXT_LIST), glob(path, recursive=True)))
    else:
        return []


def get_MD5_hash(filepath: str) -> str:
    """파일의 MD5 해시값을 구합니다.

    Args:
        filepath (str): 파일 경로

    Returns:
        str: MD5 해시값
    """

    assert os.path.isfile(filepath), "파일이 존재하지 않습니다."

    hasher = hashlib.md5()

    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            hasher.update(byte_block)
        return hasher.hexdigest()


def overwrite_small_file(originFilepath: str, destinationFilepath: str, orginFileRemove=True) -> bool:
    """원본 위치의 파일이 목적 위치의 파일 보다 작을 경우 덮어씁니다.

    Args:
        originFilepath (str): 원본 파일 경로
        destFilepath (str): 목적 위치의 파일 경로
        orginFileRemove (bool, optional): 원본 파일을 제거합니다. Defaults to True.

    Returns:
        bool: 목적 위치의 파일이 덮어써진 경우 True, 아닐 경우 False를 반환합니다.
    """

    assert os.path.isfile(originFilepath) and os.path.isfile(destinationFilepath), "원본 또는 목적 파일이 존재하지 않습니다."

    orig_file_size = os.path.getsize(originFilepath)
    dest_file_size = os.path.getsize(destinationFilepath)

    is_need_remove = orig_file_size < dest_file_size
    is_remove_success = False

    if is_need_remove:
        try:
            os.replace(originFilepath, destinationFilepath)
            is_remove_success = True
        except:
            is_remove_success = False
    elif orginFileRemove:
        try:
            os.remove(originFilepath)
        except:
            pass

    return is_remove_success


def is_str_empty_or_space(string: str) -> bool:
    if string == None or string == "" or string.isspace():
        return True
    else:
        return False
