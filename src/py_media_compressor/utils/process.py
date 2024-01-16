import platform
import subprocess
import threading
import time
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


# Windows
if platform.system() == "Windows":
    import msvcrt

# Posix (Linux, OS X)
else:
    import atexit
    import sys
    import termios
    from select import select

"""
https://stackoverflow.com/a/22085679/12745351

A Python class implementing KBHIT, the standard keyboard-interrupt poller.
Works transparently on Windows and Posix (Linux, Mac OS X).  Doesn't work
with IDLE.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

"""


class KBHit:
    def __init__(self):
        """Creates a KBHit object that you can call to do various keyboard things."""

        if platform.system() == "Windows":
            pass

        else:
            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = self.new_term[3] & ~termios.ICANON & ~termios.ECHO
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

            # Support normal-terminal reset at exit
            atexit.register(self.set_normal_term)

    def set_normal_term(self):
        """Resets to normal terminal.  On Windows this is a no-op."""

        if platform.system() == "Windows":
            pass

        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

    def getch(self):
        """Returns a keyboard character after kbhit() has been called.
        Should not be called in the same program as getarrow().
        """

        if platform.system() == "Windows":
            return msvcrt.getch().decode("utf-8")

        else:
            return sys.stdin.read(1)

    def kbhit(self):
        """Returns True if keyboard character was hit, False otherwise."""
        if platform.system() == "Windows":
            return msvcrt.kbhit()

        else:
            dr, dw, de = select([sys.stdin], [], [], 0)
            return dr != []


def process_control_wait(process: subprocess.Popen):
    """프로세스를 조작가능한 상태로 종료를 기다립니다.
    비동기적 입력 코드는 https://stackoverflow.com/a/2409034/12745351 이곳에서 참고했습니다.

    Args:
        process (subprocess.Popen): 프로세스

    Returns:
        tuple[int | Any, str | None]: 프로세스 종료 코드, 종료 상태
    """
    process_id = process.pid

    p_process = psutil.Process(process_id)

    exit_code_dict = {}
    is_process_ended = False
    is_pause = False
    result = None

    q = Queue()

    def wait_input():
        kb = KBHit()

        while not is_process_ended:
            try:
                if kb.kbhit():
                    key = kb.getch()
                    if key == "p":
                        q.put("pause")
            except Exception:
                pass
            time.sleep(0.1)

        kb.set_normal_term()

    def process_wait(exit_code_dict):
        exit_code_dict["code"] = process.wait()

    process_wait_thread = threading.Thread(target=process_wait, args=[exit_code_dict])
    input_thread = threading.Thread(target=wait_input)
    process_wait_thread.start()
    input_thread.start()

    try:
        while p_process.is_running():
            if q.empty():
                time.sleep(0.1)
            else:
                msg = q.get()
                if msg == "pause":
                    if is_pause:
                        p_process.resume()
                        is_pause = False
                    else:
                        p_process.suspend()
                        is_pause = True
    except KeyboardInterrupt:
        if p_process.is_running():
            p_process.kill()
        result = "suspend"

    is_process_ended = True
    process_wait_thread.join()
    input_thread.join()

    return (exit_code_dict.get("code"), result)


def set_low_process_priority(processid: int):
    p = psutil.Process(processid)
    if platform.system() == "Windows":
        p.nice(psutil.IDLE_PRIORITY_CLASS)
    else:
        p.nice(15)
