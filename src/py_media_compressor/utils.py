import os
import hashlib
from pprint import PrettyPrinter
import subprocess
from glob import glob
from typing import Dict, List, Tuple
import yaml


def pformat(object, indent=1, width=160, depth=None, compact=False, sort_dicts=True):  # 기본 인자값 재정의
    return PrettyPrinter(indent=indent, width=width, depth=depth, compact=compact, sort_dicts=sort_dicts).pformat(object)


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
        path = os.path.join(path, "**")

        if mediaExtFilter != None:
            ext_filter = lambda p: os.path.isfile(p) and os.path.splitext(p)[1] in mediaExtFilter
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
    """입력된 문자열이 비어있거나, 공백 또는 None 인지 확인합니다.

    Args:
        string (str): 검사할 문자열

    Returns:
        bool: 문자열이 비어있거나, 공백 또는 None일 경우 True, 아닐경우 False를 반환합니다.
    """

    return string == None or string == "" or string.isspace()


def check_command_availability(command: str) -> Tuple[bool, str, str]:
    """해당 명령이가 커맨드 라인에서 올바르게 종료되는지 체크합니다.

    Args:
        command (str): 실행할 명령어

    Returns:
        bool: 프로세스가 올바르게 종료되었을 경우 True, 아닐경우 False를 반환합니다.
    """

    exception = None

    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        result = process.wait() == 0
    except Exception as ex:
        stdout = ""
        stderr = ""
        exception = ex
        result = False

    return (result, stdout, stderr, exception)


def save_config(config: Dict, filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(config, f, Dumper=yaml.Dumper, width=100)


def load_config(filepath: str) -> Dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def string_decode(byteString: bytes, encoding="utf-8"):
    if isinstance(byteString, bytes):
        string = byteString.decode(encoding=encoding)
    else:
        string = byteString

    return string.replace("\r\n", "\n").replace("\u3000", "　")
