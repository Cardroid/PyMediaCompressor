import hashlib
import os
import platform
import shutil
from glob import escape, glob
from typing import Dict, List

import yaml


def get_media_files(path: str, useRealpath=False, mediaExtFilter: List[str] = None) -> List[str]:
    """경로에 해당하는 미디어 파일 및 폴더 내의 모든 미디어 파일을 가져옵니다.

    Args:
        path (str): 경로
        useRealpath (bool, optional): 절대 경로를 사용합니다. Defaults to False.
        mediaExtFilter (List[str], optional): 확장자 필터. Defaults to None.

    Returns:
        List[str]: 파일의 목록을 반환합니다.
    """

    if useRealpath:
        path = os.path.realpath(path)

    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        path = os.path.join(escape(path), "**")

        if mediaExtFilter is not None:
            ext_filter = lambda p: os.path.isfile(p) and os.path.splitext(p)[1].lower() in mediaExtFilter
        else:
            ext_filter = lambda p: os.path.isfile(p)

        return list(filter(ext_filter, glob(path, recursive=True)))
    else:
        return []


def get_MD5_hash(filepath: str, blockSize: int = 65536) -> str:
    """파일의 MD5 해시값을 구합니다.

    Args:
        filepath (str): 파일 경로
        blockSize (int, optional): 한 번에 읽어올 파일의 블록 크기

    Returns:
        str: MD5 해시값
    """

    assert os.path.isfile(filepath), "파일이 존재하지 않습니다."

    hasher = hashlib.md5()

    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(blockSize), b""):
            hasher.update(byte_block)
        return hasher.hexdigest()


def overwrite_small_file(originFilepath: str, destinationFilepath: str, orginFileRemove=True) -> bool:
    """원본 위치의 파일이 목적 위치의 파일 보다 작을 경우 덮어씁니다.

    Args:
        originFilepath (str): 원본 파일 경로
        destinationFilepath (str): 목적 위치의 파일 경로
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
            move(originFilepath, destinationFilepath)
            is_remove_success = True
        except Exception:
            is_remove_success = False
    elif orginFileRemove:
        try:
            remove(originFilepath)
        except Exception:
            pass

    return is_remove_success


def set_file_permission(path: str, permissions=0o775):
    if platform.system() == "Linux" and os.path.isfile(path):
        os.chmod(path, permissions)


def save_config(config: Dict, filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(config, f, Dumper=yaml.Dumper, width=100, sort_keys=False)
    set_file_permission(filepath)


def load_config(filepath: str) -> Dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def move(sourcePath, destPath):
    shutil.move(sourcePath, destPath)


def remove(path):
    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        raise FileNotFoundError(path)
