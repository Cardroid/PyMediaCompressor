from typing import Any, Dict, List

import ffmpeg

from py_media_compressor.common import DictDataExtendBase
from py_media_compressor.model import FileInfo, EncodeOption


class FFmpegArgs(DictDataExtendBase):
    def __init__(self, fileInfo: FileInfo, encodeOption: EncodeOption = EncodeOption(), metadatas: Dict = {}) -> None:
        assert isinstance(fileInfo, FileInfo)
        assert isinstance(encodeOption, EncodeOption)
        assert isinstance(metadatas, dict)

        # 사용자 정의 메타 데이터 사용 가능 (-movflags use_metadata_tags)
        # 해당 옵션이 없으면 스트림 카피로도 메타 데이터가 누락됨
        super().__init__(data={"movflags": "use_metadata_tags"})

        self._metadatas = metadatas
        self._encode_option = encodeOption

        self._file_info = fileInfo
        self._probe_info = ffmpeg.probe(self.file_info.input_filepath)

        self._video_stream = None
        self._audio_streams = []
        for stream in self.probe_info["streams"]:
            if self._video_stream == None and stream["codec_type"] == "video" and stream["codec_name"] not in ["png"]:
                self._video_stream = stream
            elif stream["codec_type"] == "audio":
                self._audio_streams.append(stream)

    def _as_dict(self) -> Dict[str, Any]:
        result = super()._as_dict()
        result["filename"] = self.file_info.output_filepath
        return result

    def get_all_in_one_dict(self):  # 디버깅 용
        return {
            "encode_option": self._encode_option.as_dict(),
            "file_info": self._file_info.as_dict(),
            "probe_info": self._probe_info,
            "metadatas": self._metadatas,
        }

    @property
    def encode_option(self):
        return self._encode_option

    @property
    def file_info(self):
        return self._file_info

    @property
    def probe_info(self) -> Dict:
        return self._probe_info

    @property
    def video_stream(self) -> Dict:
        return self._video_stream

    @property
    def audio_streams(self) -> List[Dict]:
        return self._audio_streams

    @property
    def is_only_audio(self) -> bool:
        return self._video_stream == None and len(self.audio_streams) > 0

    @property
    def expected_ext(self) -> str:
        return ".m4a" if self.is_only_audio else ".mp4"
