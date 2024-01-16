from enum import Flag, auto, unique


@unique
class LogDestination(Flag):
    CONSOLE = auto()
    FILE = auto()
    ALL = CONSOLE | FILE

    def is_flag(self, item: Flag) -> bool:
        return (self.value & item.value) != 0

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_
