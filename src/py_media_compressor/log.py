import inspect
import logging
import logging.config
import logging.handlers
import os
import re
import sys
from typing import Callable, Dict, Union

import colorlog
import tqdm

from py_media_compressor import utils
from py_media_compressor.model.enum import LogDestination, LogLevel
from py_media_compressor.version import package_name


def unhandled_exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    get_logger(unhandled_exception_hook).critical(
        "처리되지 않은 예외가 발생했습니다.", exc_info=(exc_type, exc_value, exc_traceback)
    )


sys.excepthook = unhandled_exception_hook

# 전역 설정
# config_filepath (str, optional): 로그 설정 파일 저장 경로. Defaults to "config/log.yaml".
# level (int, optional): 출력 로그 레벨. Defaults to INFO.
# dir (str, optional): 로그파일 저장 디렉토리 경로. Defaults to "logs".
# use_console (bool, optional): 콘솔 출력 사용 여부. Defaults to True.
# use_rotatingfile (bool, optional): 파일 출력 사용 여부. Defaults to True.
SETTINGS = {
    "config_filepath": "config/log.yaml",
    "level": LogLevel.INFO,
    "dir": "logs",
    "use_console": True,
    "use_rotatingfile": True,
}

# 전역 로깅 위치 설정
LogDest = LogDestination.ALL


def get_logger(name: Union[str, Callable], logLevel: LogLevel = LogLevel.DEFAULT) -> logging.Logger:
    """로거를 생성합니다.

    Args:
        name (Union[str, Callable]): 로거 이름 또는 호출 함수
        logLevel (LogLevel, optional): 출력 로그 레벨. Default value is the value of SETTINGS.

    Returns:
        logging.Logger: 로거
    """

    global SETTINGS

    if callable(name):
        frm = inspect.stack()[1]
        path = os.path.normpath(os.path.splitext(frm.filename)[0])
        module_path = path.split(os.sep)
        paths = []
        for path_name in reversed(module_path):
            if path_name == package_name:
                break
            paths.append(path_name)
        paths.append(name.__name__)
        name = ".".join(paths)

    os.makedirs(SETTINGS["dir"], exist_ok=True)

    if not logging.root.hasHandlers():
        root_logger_setup()

    logLevel = logLevel.value
    if logLevel < 0:
        logLevel = SETTINGS["level"].value

    logger = logging.getLogger(name)
    logger.setLevel(logLevel)

    return logger


def get_default_config() -> Dict:
    global SETTINGS

    using_root_handlers = []
    if SETTINGS["use_console"]:
        using_root_handlers.append("console")
    if SETTINGS["use_rotatingfile"]:
        using_root_handlers.append("file")
        using_root_handlers.append("warn_file")

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
            "warn_dest_file_filter": {
                "()": get_fullname(HandlerDestFilter),
                "mode": LogDestination.FILE.name,
                "logLevel": LogLevel.WARNING.name,
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
                "()": get_fullname(ConsoleLoggingHandler),
                "formatter": "colored_console",
                "filters": ["dest_console_filter"],
                "useTqdm": True,
            },
            "file": {
                "()": get_fullname(logging.handlers.TimedRotatingFileHandler),
                "formatter": "detail",
                "filters": ["dest_file_filter"],
                "filename": os.path.join(SETTINGS["dir"], "output.log"),
                # "maxBytes": 20 * 1024 * 1024,  # 20MB
                "when": "H",
                "interval": 6,
                "backupCount": 20,
                "encoding": "utf-8",
            },
            "warn_file": {
                "()": get_fullname(logging.handlers.TimedRotatingFileHandler),
                "formatter": "detail",
                "filters": ["warn_dest_file_filter"],
                "filename": os.path.join(SETTINGS["dir"], "error.log"),
                # "maxBytes": 20 * 1024 * 1024,  # 20MB
                "when": "H",
                "interval": 6,
                "backupCount": 30,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": logging.getLevelName(SETTINGS["level"].value),
            "handlers": using_root_handlers,
        },
    }

    return config


def root_logger_setup():
    global SETTINGS

    if not utils.is_str_empty_or_space(SETTINGS["config_filepath"]):
        try:
            config = utils.load_config(SETTINGS["config_filepath"])

            is_enabled = config.get("enabled")
            if is_enabled is None:
                is_enabled = True
            else:
                del config["enabled"]

            if is_enabled:
                logging.config.dictConfig(config)
            else:
                logging.root.addHandler(logging.NullHandler())

            if is_enabled and not logging.root.hasHandlers():
                raise Exception("하나 이상의 Log Handler가 필요합니다.")

            logger = get_logger(root_logger_setup)

            logger.debug("설정 파일 로드 완료")
        except Exception:
            is_enabled = True
            config = get_default_config()
            logging.config.dictConfig(config)

            logger = get_logger(root_logger_setup)

            logger.warning("설정 파일 로드 오류, 기본 설정이 사용됩니다.", exc_info=True)

    if not utils.is_str_empty_or_space(SETTINGS["config_filepath"]):
        config["enabled"] = is_enabled
        utils.save_config(config, SETTINGS["config_filepath"])
        logger.debug("설정 파일 저장 완료")


# 출처: https://stackoverflow.com/a/38739634/12745351
# 수정해서 사용함
class ConsoleLoggingHandler(logging.StreamHandler):
    def __init__(self, useTqdm: bool = True):
        super().__init__()
        self._use_tqdm = useTqdm

    def emit(self, record):
        if self._use_tqdm:
            try:
                msg = self.format(record)
                tqdm.tqdm.write(msg)
                self.flush()
            except Exception:
                self.handleError(record)
        else:
            super().emit(record)


class HandlerDestFilter(logging.Filter):
    LINE_FORMATTER_REGEX = re.compile(r"\n(?!\t-> )")

    def __init__(
        self,
        name: str = "",
        mode: Union[int, str, LogDestination] = LogDestination.ALL,
        logLevel: Union[int, str, LogLevel] = LogLevel.DEFAULT,
    ) -> None:
        super().__init__(name)

        if isinstance(mode, int):
            assert LogDestination.has_value(mode), "지원하지 않는 mode 입니다."
            self.mode = LogDestination(mode)
        elif isinstance(mode, str):
            assert LogDestination.has_name(mode), "지원하지 않는 mode 입니다."
            self.mode = LogDestination[mode]
        else:
            assert mode in LogDestination, "지원하지 않는 mode 입니다."
            self.mode = mode

        if isinstance(logLevel, int):
            assert LogLevel.has_value(logLevel), "지원하지 않는 LogLevel 입니다."
            self.log_level = LogLevel(logLevel)
        elif isinstance(logLevel, str):
            assert LogLevel.has_name(logLevel), "지원하지 않는 LogLevel 입니다."
            self.log_level = LogLevel[logLevel]
        else:
            assert logLevel in LogLevel, "지원하지 않는 LogLevel 입니다."
            self.log_level = logLevel

    def filter(self, record: logging.LogRecord):
        if record.levelno < self.log_level:
            return False

        self._format_line(record=record)
        if len(record.args) > 0 and isinstance(dest := record.args.get("dest"), LogDestination):
            del record.args["dest"]
            return self.mode.is_flag(dest)
        else:
            return self.mode.is_flag(LogDest)

    def _format_line(self, record: logging.LogRecord):
        record.msg = self.LINE_FORMATTER_REGEX.sub("\n\t-> ", record.msg)
