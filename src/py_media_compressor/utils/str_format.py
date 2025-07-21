from pprint import PrettyPrinter
from typing import Union

from py_media_compressor import log


def pformat(object, indent=1, width=160, depth: Union[int, None] = None, compact=False, sort_dicts=True):  # 기본값 재정의
    if isinstance(object, list):
        object = _pformat_list_helper(object=object, depth=depth)
    else:
        object = _pformat_filer(object=object)

    return PrettyPrinter(indent=indent, width=width, depth=depth, compact=compact, sort_dicts=sort_dicts).pformat(
        object
    )


def _pformat_list_helper(object, depth=None, idx=0):
    if idx > depth if depth is not None else idx > 10:
        return object

    result = []
    for obj in object:
        if isinstance(obj, list):
            result.append(_pformat_list_helper(obj, depth=depth, idx=idx + 1))
        else:
            result.append(_pformat_filer(obj))

    return result


def _pformat_filer(object):
    from py_media_compressor.common import DictBase

    if issubclass(type(object), DictBase):
        object = object.as_dict()

    return object


def is_str_empty_or_space(string: str) -> bool:
    """입력된 문자열이 비어있거나, 공백 또는 None 인지 확인합니다.

    Args:
        string (str): 검사할 문자열

    Returns:
        bool: 문자열이 비어있거나, 공백 또는 None일 경우 True, 아닐경우 False를 반환합니다.
    """

    return string is None or string == "" or string.isspace()


def string_decode(byteString: bytes, encoding="utf-8"):
    if isinstance(byteString, bytes):
        try:
            string = byteString.decode(encoding=encoding)
        except Exception:
            log.get_logger(string_decode).error(
                f"디코드 오류, 바이트를 디코드 할 수 없었습니다.\nEncoding: {encoding}\nByteString: {byteString}",
                exc_info=True,
            )
            return ""
    else:
        string = byteString

    return string.replace("\r\n", "\n").replace("\u3000", "　")
