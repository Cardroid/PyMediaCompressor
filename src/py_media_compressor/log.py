import os
from enum import Enum, Flag, auto, unique
import logging
import logging.handlers
import logging.config
import re
from typing import Dict, Union
import colorlog

from py_media_compressor import utils

# 로그 레벨 정의
CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG

LOGLEVEL_DICT = {
    "critical": CRITICAL,
    "error": ERROR,
    "warning": WARNING,
    "info": INFO,
    "debug": DEBUG,
}


@unique
class LogDestination(Flag):
    CONSOLE = auto()
    FILE = auto()
    ALL = CONSOLE | FILE

    @staticmethod
    def is_flag(item1: Enum, item2: Enum) -> bool:
        return (item1.value & item2.value) != 0

    def is_flag(self, item: Enum) -> bool:
        return (self.value & item.value) != 0

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_


# 전역 설정
# level (int, optional): 출력 로그 레벨. Defaults to INFO.
# dir (str, optional): 로그파일 저장 디렉토리 경로. Defaults to "logs".
# use_console (bool, optional): 콘솔 출력 사용 여부. Defaults to True.
# use_rotatingfile (bool, optional): 파일 출력 사용 여부. Defaults to True.
SETTINGS = {
    "config_filepath": "config/log.yaml",
    "dir": "logs",
    "level": INFO,
    "use_console": True,
    "use_rotatingfile": True,
}

# 전역 로깅 위치 설정
LogDest = LogDestination.ALL


def get_logger(name: str, logLevel: int = -1) -> logging.Logger:
    """로거를 생성합니다.

    Args:
        name (str): 로거 이름
        logLevel (int, optional): 출력 로그 레벨. Default value is the value of SETTINGS.

    Returns:
        logging.Logger: 로거
    """

    os.makedirs(SETTINGS["dir"], exist_ok=True)

    if not logging.root.hasHandlers():
        root_logger_setup()

    if logLevel < 0:
        logLevel = SETTINGS["level"]

    logger = logging.getLogger(name)
    logger.setLevel(logLevel)

    return logger


def get_default_config() -> Dict:
    using_root_handlers = []
    if SETTINGS["use_console"]:
        using_root_handlers.append("console")
    if SETTINGS["use_rotatingfile"]:
        using_root_handlers.append("file")

    get_fullname = lambda c: c.__qualname__ if (module := c.__module__) == "builtins" else module + "." + c.__qualname__

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "dest_console_filter": {
                "()": get_fullname(HandlerDestFilter),
                "mode": LogDestination.CONSOLE.name,
            },
            "dest_file_filter": {
                "()": get_fullname(HandlerDestFilter),
                "mode": LogDestination.FILE.name,
            },
        },
        "formatters": {
            "detail": {
                "format": "%(asctime)s %(levelname)-8s [%(name)s] [%(thread)d][%(filename)s:%(lineno)d] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "colored_console": {
                "()": get_fullname(colorlog.ColoredFormatter),
                "format": "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s [%(name)s] [%(thread)d][%(filename)s:%(lineno)d] %(log_color)s%(message)s%(reset)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "bold_red",
                    "CRITICAL": "bold_red,bg_white",
                },
            },
        },
        "handlers": {
            "console": {
                "()": get_fullname(logging.StreamHandler),
                "formatter": "colored_console",
                "filters": ["dest_console_filter"],
            },
            "file": {
                "()": get_fullname(logging.handlers.RotatingFileHandler),
                "formatter": "detail",
                "filters": ["dest_file_filter"],
                "filename": os.path.join(SETTINGS["dir"], "output.log"),
                "maxBytes": 20 * 1024 * 1024,  # 20MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {
                "level": logging.getLevelName(SETTINGS["level"]),
                "handlers": using_root_handlers,
            }
        },
    }

    return config


def root_logger_setup():
    is_config_load_from_file = False
    exception = None

    if not utils.is_str_empty_or_space(SETTINGS["config_filepath"]):
        try:
            config = utils.load_config(SETTINGS["config_filepath"])
            is_config_load_from_file = True
        except Exception as ex:
            exception = ex

    if not is_config_load_from_file:
        config = get_default_config()

    logging.config.dictConfig(config)

    logger = logging.getLogger("log")

    if is_config_load_from_file:
        logger.debug(f"설정 파일 로드 완료")
    elif exception != None:
        logger.warning(f"설정 파일 로드 오류, 기본 설정 사용됨 \n{exception}")
    else:
        logger.debug(f"기본 설정 로드 완료")

    if not utils.is_str_empty_or_space(SETTINGS["config_filepath"]):
        utils.save_config(config, SETTINGS["config_filepath"])
        logger.debug(f"설정 파일 저장 완료")


class HandlerDestFilter(logging.Filter):
    LINE_FORMATTER_REGEX = re.compile(r"\n(?!\t-> )")

    def __init__(self, name: str = "", mode: Union[int, str, LogDestination] = LogDestination.ALL) -> None:
        super().__init__(name)

        if isinstance(mode, int):
            assert LogDestination.has_value(mode), f"지원하지 않는 mode 입니다."
            self.mode = LogDestination(mode)
        elif isinstance(mode, str):
            assert LogDestination.has_name(mode), f"지원하지 않는 mode 입니다."
            self.mode = LogDestination[mode]
        else:
            assert mode in LogDestination, f"지원하지 않는 mode 입니다."
            self.mode = mode

    def filter(self, record: logging.LogRecord):
        self._format_line(record=record)
        if len(record.args) > 0 and isinstance(dest := record.args.get("dest", None), LogDestination):
            del record.args["dest"]
            return self.mode.is_flag(dest)
        else:
            return self.mode.is_flag(LogDest)

    def _format_line(self, record: logging.LogRecord):
        record.msg = self.LINE_FORMATTER_REGEX.sub("\n\t-> ", record.msg)
