from py_media_compressor.common import DictDataBase


class EncodeOption(DictDataBase):
    def __init__(
        self,
        maxHeight: int = 1440,
        isForce: bool = False,
        codec: str = "h.264",
        crf: int = -1,
        removeErrorOutput: bool = True,
        useProgressbar: bool = False,
        leave: bool = True,
    ) -> None:
        """인코드 옵션

        Args:
            maxHeight (int, optional): 미디어의 최대 세로 픽셀. Defaults to 1440.
            isForce (bool, optional): 이미 처리된 미디어 파일을 강제적으로 재처리합니다. Defaults to False.
            codec (str, optional): 압축 모드. Defaults to "h.264".
            crf (int, optional): 압축 crf 값. Defaults to -1.
            removeErrorOutput (bool, optional): 정상적으로 압축하지 못했을 경우 출력 파일을 삭제합니다. Defaults to True.
            useProgressbar (bool, optional): 진행바 사용 여부. Defaults to False.
            leave (bool, optional): 중첩된 진행바를 사용할 경우, False 를 권장합니다. Defaults to True.
        """

        assert isinstance(maxHeight, int)
        assert isinstance(isForce, bool)
        assert codec in ["h.264", "h.265"]
        assert isinstance(crf, int)
        assert isinstance(removeErrorOutput, bool)
        assert isinstance(useProgressbar, bool)
        assert isinstance(leave, bool)

        if crf < 0:
            if codec == "h.264":
                crf = 23
            elif codec == "h.265":
                crf = 28

        super().__init__(
            data={
                "max_height": maxHeight,
                "is_force": isForce,
                "codec": codec,
                "crf": crf,
                "remove_error_output": removeErrorOutput,
                "use_progressbar": useProgressbar,
                "leave": leave,
            }
        )

    def clone(self):
        clone_option = EncodeOption()
        clone_option._data = self.as_clone_dict()  # TODO: 더 좋은 방법을 사용할 수 있으면 수정필요
        return clone_option

    @property
    def max_height(self) -> int:
        return self._get_value()

    @property
    def is_force(self) -> bool:
        return self._get_value()

    @property
    def codec(self) -> str:
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
