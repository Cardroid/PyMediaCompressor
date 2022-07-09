import os
import logging
import logging.handlers
from colorlog import ColoredFormatter

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


def get_logger(name: str, dirpath="PyMediaCompressor_logs", logLevel=INFO, useConsole=True, useRotatingfile=True) -> logging.Logger:
    """로거를 생성합니다.

    Args:
        name (str): 로거 이름
        dirpath (str, optional): 로그파일 저장 디렉토리 경로. Defaults to "PyMediaCompressor_logs".
        log_level (int, optional): 출력 로그 레벨. Defaults to INFO.
        use_console (bool, optional): 콘솔 출력 사용 여부. Defaults to True.
        use_rotatingfile (bool, optional): 파일 출력 사용 여부. Defaults to True.

    Returns:
        logging.Logger: 로거
    """

    logger = logging.getLogger(name)
    logger.propagate = False
    logger.setLevel(logLevel)

    if useConsole:
        colored_console_handler = logging.StreamHandler()
        colored_console_handler.setFormatter(
            ColoredFormatter(
                fmt="%(asctime)s %(log_color)s%(levelname)-8s%(reset)s [%(name)s] [%(filename)s:%(lineno)d] %(log_color)s%(message)s%(reset)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "bold_red",
                    "CRITICAL": "bold_red,bg_white",
                },
            )
        )
        logger.addHandler(colored_console_handler)

    if useRotatingfile:
        os.makedirs(dirpath, exist_ok=True)

        log_max_size = 20 * 1024 * 1024  # 20MB
        log_file_count = 10
        rotating_file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(dirpath, "output.log"),
            maxBytes=log_max_size,
            backupCount=log_file_count,
            encoding="utf-8",
        )
        rotating_file_handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(levelname)-8s [%(name)s] [%(filename)s:%(lineno)d] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(rotating_file_handler)

    return logger
