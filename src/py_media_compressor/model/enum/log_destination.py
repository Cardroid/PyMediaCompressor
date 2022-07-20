from enum import Flag, auto, unique


@unique
class LogDestination(Flag):
    CONSOLE = auto()
    FILE = auto()
    ALL = CONSOLE | FILE

    @staticmethod
    def is_flag(item1: Flag, item2: Flag) -> bool:
        return (item1.value & item2.value) != 0

    def is_flag(self, item: Flag) -> bool:
        return (self.value & item.value) != 0

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name: str) -> bool:
        return name in cls._member_map_
