from enum import Enum, auto, unique


@unique
class FileTaskStatus(Enum):
    INIT = auto()  # 초기 값
    WAITING = auto()  # 대기 중
    PROCESSING = auto()  # 처리 중
    SKIPPED = auto()  # 스킵
    SUCCESS = auto()  # 성공
    ERROR = auto()  # 오류

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_
