from typing import Any, Dict, List

import ffmpeg

from py_media_compressor.common import DictDataExtendBase
from py_media_compressor.const import IGNORE_STREAM_FILTER
from py_media_compressor.model import EncodeOption, FileInfo


class FFmpegArgs(DictDataExtendBase):
    def __init__(self, fileInfo: FileInfo, encodeOption: EncodeOption = EncodeOption(), metadatas: Dict = {}) -> None:
        assert isinstance(fileInfo, FileInfo)
        assert isinstance(encodeOption, EncodeOption)
        assert isinstance(metadatas, dict)

        super().__init__()

        self._metadatas = metadatas
        self._encode_option = encodeOption

        self._file_info = fileInfo
        self._probe_info = ffmpeg.probe(self.file_info.input_filepath)

        self._video_stream = None
        self._audio_streams = []

        streams = self.probe_info.get("streams")

        assert streams is not None, "스트림을 불러올 수 없습니다."

        for stream in streams:
            if (
                self._video_stream is not None
                and stream["codec_type"] == "video"
                and stream["codec_name"] not in IGNORE_STREAM_FILTER
            ):
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
        return self._video_stream is None and len(self.audio_streams) > 0

    @property
    def expected_ext(self) -> str:
        return ".m4a" if self.is_only_audio else ".mp4"
