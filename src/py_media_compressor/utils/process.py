import platform
import subprocess
from typing import Tuple

import psutil

from py_media_compressor.utils import string_decode


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

    return (result, string_decode(stdout), string_decode(stderr), exception)


def set_low_process_priority(processid: int):
    p = psutil.Process(processid)
    if platform.system() == "Windows":
        p.nice(psutil.IDLE_PRIORITY_CLASS)
    else:
        p.nice(15)
