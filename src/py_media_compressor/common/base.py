import inspect
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import Any, Dict, Union

from py_media_compressor.utils import pformat


class DictBase(metaclass=ABCMeta):
    @abstractmethod
    def _as_dict(self) -> Dict[str, Any]:
        pass

    def as_dict(self) -> Dict[str, Any]:
        return self._as_dict()

    def as_clone_dict(self) -> Dict[str, Any]:
        return deepcopy(self._as_dict())

    def __str__(self) -> str:
        data = self.as_dict()
        if data != None:
            return pformat(data)
        else:
            return super().__str__()


class DictDataBase(DictBase):
    def __init__(self) -> None:
        super().__init__()
        self._data = {}

    def _as_dict(self) -> Dict[str, Any]:
        return self._data

    def __get_func_name(self, deep: int = 2):
        return inspect.stack(0)[deep][3]

    def _get_value(self, key: Union[str, None] = None, default=None, deep: int = 2):
        return self._data.get(self.__get_func_name(deep=deep) if key == None else key, default)

    def _set_value(self, value, key: Union[str, None] = None, deep: int = 2):
        self._data[self.__get_func_name(deep=deep) if key == None else key] = value

    def _set_value_pipe(self, value, key: Union[str, None] = None, deep: int = 3):
        self._set_value(value=value, key=key, deep=deep)
        return value


class DictDataExtendBase(DictDataBase):
    def __init__(self) -> None:
        super().__init__()

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, value):
        self._data[key] = value

    def __delitem__(self, key: str):
        del self._data[key]
