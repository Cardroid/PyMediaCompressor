import os

from py_media_compressor import utils
from py_media_compressor.common import DictDataBase
from py_media_compressor.model.enum.file_task_status import FileTaskStatus


class FileInfo(DictDataBase):
    def __init__(self, inputFilepath: str) -> None:
        super().__init__()

        self._data = {"input_filepath": inputFilepath}

        assert self.is_input_file_exist, f"입력 파일이 존재하지 않습니다. Filepath: {inputFilepath}"

        self.output_filepath = ""
        self.status = FileTaskStatus.INIT

        self.__input_file_MD5_size = 0
        self.__output_file_MD5_size = 0

    @property
    def input_filepath(self) -> str:
        return self._get_value()

    @property
    def output_filepath(self) -> str:
        return self._get_value()

    @output_filepath.setter
    def output_filepath(self, outputFilepath: str):
        self._set_value(outputFilepath)

    @property
    def is_input_file_exist(self):
        return os.path.isfile(self.input_filepath)

    @property
    def is_output_file_exist(self):
        return os.path.isfile(self.output_filepath)

    @property
    def input_filesize(self) -> int:
        if self.is_input_file_exist:
            return self._set_value_pipe(os.path.getsize(self.input_filepath))
        else:
            return self._set_value_pipe(0)

    @property
    def output_filesize(self) -> int:
        if self.is_output_file_exist:
            return self._set_value_pipe(os.path.getsize(self.output_filepath))
        else:
            return self._set_value_pipe(0)

    @property
    def status(self) -> FileTaskStatus:
        return self._get_value()

    @status.setter
    def status(self, status: FileTaskStatus):
        self._set_value(status)

    @property
    def input_file_MD5(self) -> str:
        md5 = self._get_value()

        if (
            utils.is_str_empty_or_space(md5) or self.__input_file_MD5_size == self.input_filesize
        ):  # 값의 신뢰도를 위해 이전 파일 크기와 현재 파일 크기가 같은지도 확인
            md5 = utils.get_MD5_hash(self.input_filepath, useProgressbar=True)
            self.__input_file_MD5_size = self.input_filesize
            self._set_value(md5)

        return md5

    @property
    def output_file_MD5(self) -> str:
        md5 = self._get_value()

        if (
            utils.is_str_empty_or_space(md5) or self.__output_file_MD5_size == self.output_filesize
        ):  # 값의 신뢰도를 위해 이전 파일 크기와 현재 파일 크기가 같은지도 확인
            md5 = utils.get_MD5_hash(self.output_filepath, useProgressbar=True)
            self.__output_file_MD5_size = self.output_filesize
            self._set_value(md5)

        return md5
