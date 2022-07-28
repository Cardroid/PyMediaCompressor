from enum import Enum, unique
import logging


@unique
class LogLevel(Enum):
    DEFAULT = -1
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_

    def __hash__(self):
        return self.value

    def __lt__(self, other):
        if isinstance(other, int):
            return self.value < other
        else:
            return super().__lt__(other)

    def __le__(self, other):
        if isinstance(other, int):
            return self.value <= other
        else:
            return super().__le__(other)

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == other
        else:
            return super().__eq__(other)

    def __ne__(self, other):
        if isinstance(other, int):
            return self.value != other
        else:
            return super().__ne__(other)

    def __gt__(self, other):
        if isinstance(other, int):
            return self.value > other
        else:
            return super().__gt__(other)

    def __ge__(self, other):
        if isinstance(other, int):
            return self.value >= other
        else:
            return super().__ge__(other)
