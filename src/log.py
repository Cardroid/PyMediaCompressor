import os
import logging
import logging.handlers
import logging.config
from typing import Dict
from colorlog import ColoredFormatter
import yaml

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


def get_logger(name: str, logLevel: int = -1) -> logging.Logger:
    """로거를 생성합니다.

    Args:
        name (str): 로거 이름

    Returns:
        logging.Logger: 로거
    """

    if not logging.root.hasHandlers():
        root_logger_setup()

    if logLevel < 0:
        logLevel = SETTINGS["level"]

    logger = logging.getLogger(name)
    logger.setLevel(logLevel)

    return logger


def get_default_config() -> Dict:
    os.makedirs(SETTINGS["dir"], exist_ok=True)

    using_root_handlers = []
    if SETTINGS["use_console"]:
        using_root_handlers.append("console")
    if SETTINGS["use_rotatingfile"]:
        using_root_handlers.append("file")

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "colored_console": {
                "class": "colorlog.ColoredFormatter",
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
            "detail": {"format": "%(asctime)s %(levelname)-8s [%(name)s] [%(thread)d][%(filename)s:%(lineno)d] - %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "colored_console"},
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detail",
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


def save_config(config: Dict, filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(config, f, encoding="utf-8")


def load_config(filepath: str) -> Dict:
    with open(filepath, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config


def root_logger_setup():
    exception = None

    try:
        config = load_config(SETTINGS["config_filepath"])
    except Exception as ex:
        exception = ex
        config = get_default_config()

    logging.config.dictConfig(config)

    logger = logging.getLogger("log")

    if exception != None:
        logger.warning(f"설정 파일 로드 오류, 기본 설정 사용됨 \n\t{exception}")
    else:
        logger.debug(f"설정 파일 로드 완료")
