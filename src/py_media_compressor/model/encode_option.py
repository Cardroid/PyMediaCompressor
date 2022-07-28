from py_media_compressor.common import DictDataBase


class EncodeOption(DictDataBase):
    def __init__(
        self,
        maxHeight: int = 1440,
        isForce: bool = False,
        compressionMode: str = "h.264",
        crf: int = 23,
        removeErrorOutput: bool = True,
        useProgressbar: bool = False,
        leave: bool = True,
    ) -> None:
        """인코드 옵션

        Args:
            maxHeight (int, optional): 미디어의 최대 세로 픽셀. Defaults to 1440.
            isForce (bool, optional): 이미 처리된 미디어 파일을 강제적으로 재처리합니다. Defaults to False.
            compressionMode (str, optional): 압축 모드. Defaults to "h.264".
            crf (int, optional): 압축 crf 값. Defaults to 23.
            removeErrorOutput (bool, optional): 정상적으로 압축하지 못했을 경우 출력 파일을 삭제합니다. Defaults to True.
            useProgressbar (bool, optional): 진행바 사용 여부. Defaults to False.
            leave (bool, optional): 중첩된 진행바를 사용할 경우, False 를 권장합니다. Defaults to True.
        """

        assert isinstance(maxHeight, int)
        assert isinstance(isForce, bool)
        assert isinstance(compressionMode, str)
        assert isinstance(crf, int)
        assert isinstance(removeErrorOutput, bool)
        assert isinstance(useProgressbar, bool)
        assert isinstance(leave, bool)

        super().__init__(
            data={
                "max_height": maxHeight,
                "is_force": isForce,
                "compression_mode": compressionMode,
                "crf": crf,
                "remove_error_output": removeErrorOutput,
                "use_progressbar": useProgressbar,
                "leave": leave,
            }
        )

    @property
    def max_height(self) -> int:
        return self._get_value()

    @property
    def is_force(self) -> bool:
        return self._get_value()

    @property
    def compression_mode(self) -> str:
        return self._get_value()

    @property
    def crf(self) -> int:
        return self._get_value()

    @property
    def remove_error_output(self) -> bool:
        return self._get_value()

    @property
    def use_progressbar(self) -> bool:
        return self._get_value()

    @property
    def leave(self) -> bool:
        return self._get_value()
