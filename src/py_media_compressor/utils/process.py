import time
import platform
import threading
import subprocess
from queue import Queue
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


def process_wait(process: subprocess.Popen):
    process_id = process.pid

    p_process = psutil.Process(process_id)

    is_process_ended = False
    is_pause = False
    result = None

    q = Queue()

    if platform.system() == "Windows":
        # Windows용 코드
        import msvcrt

        def getkey():
            if msvcrt.kbhit():
                return msvcrt.getch()

    else:
        # Linux & Mac 용 코드
        import sys, select, tty, termios

        def isData():
            return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

        def getkey():
            original_attributes = termios.tcgetattr(sys.stdin)
            ch = None
            try:
                tty.setcbreak(sys.stdin.fileno())
                if isData():
                    ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_attributes)
            return ch

    def wait_input():
        while not is_process_ended:
            key = getkey()
            if key == b"p":
                q.put("pause")
                time.sleep(1)
            elif key == b"\x03":
                q.put("suspend")
            time.sleep(1)

    input_thread = threading.Thread(target=wait_input)
    input_thread.start()

    while p_process.is_running():
        if q.empty():
            time.sleep(1)
        else:
            msg = q.get()
            if msg == "pause":
                if is_pause:
                    p_process.resume()
                    is_pause = False
                else:
                    p_process.suspend()
                    is_pause = True
            elif msg == "suspend":
                p_process.kill()
                result = "suspend"

    is_process_ended = True
    input_thread.join()

    return (process.returncode, result)


def set_low_process_priority(processid: int):
    p = psutil.Process(processid)
    if platform.system() == "Windows":
        p.nice(psutil.IDLE_PRIORITY_CLASS)
    else:
        p.nice(15)
