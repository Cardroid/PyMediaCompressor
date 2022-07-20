# 인코더 표식
PROCESSER_NAME = "Automatic media compression processed"
PROCESSER_TAG_END = "AMCP_END"


# 사용자 지정 파일확장자 필터
FILE_EXT_FILTER_LIST = [
    ".3gp",
    ".3g2",
    ".aif",
    ".aac",
    ".ac3",
    ".avi",
    ".flac",
    ".flv",
    ".webm",
    ".mkv",
    ".mov",
    ".m4v",
    ".mp4",
    ".m4a",
    ".mp2",
    ".mp3",
    ".ogg",
    ".mpg",
    ".mpeg",
    ".ts",
    ".m3u8",
    ".asf",
    ".wav",
    ".wmv",
    ".wma",
]


# ffmpeg 입력 가능 파일확장자
DEMUXER_FILE_EXT_LIST = list(
    set(
        FILE_EXT_FILTER_LIST
        + [
            ".str",
            ".aa",
            ".aac",
            ".ac3",
            ".acm",
            ".adf",
            ".adp",
            ".dtk",
            ".ads",
            ".ss2",
            ".adx",
            ".aea",
            ".afc",
            ".aix",
            ".al",
            ".ape",
            ".apl",
            ".mac",
            ".aqt",
            ".ast",
            ".avi",
            ".avs",
            ".avr",
            ".bfstm",
            ".bcstm",
            ".bin",
            ".bit",
            ".bmv",
            ".brstm",
            ".cdg",
            ".cdxl",
            ".xl",
            ".302",
            ".daud",
            ".str",
            ".dss",
            ".dts",
            ".dtshd",
            ".dv",
            ".dif",
            ".cdata",
            ".eac3",
            ".paf",
            ".fap",
            ".flm",
            ".flac",
            ".flv",
            ".fsb",
            ".g722",
            ".722",
            ".tco",
            ".rco",
            ".g723_1",
            ".g729",
            ".genh",
            ".gsm",
            ".h261",
            ".h26l",
            ".h264",
            ".264",
            ".avc",
            ".hevc",
            ".h265",
            ".265",
            ".idf",
            ".cgi",
            ".sf",
            ".ircam",
            ".ivr",
            ".669",
            ".amf",
            ".ams",
            ".dbm",
            ".digi",
            ".dmf",
            ".dsm",
            ".far",
            ".gdm",
            ".imf",
            ".it",
            ".j2b",
            ".m15",
            ".mdl",
            ".med",
            ".mmcmp",
            ".mms",
            ".mo3",
            ".mod",
            ".mptm",
            ".mt2",
            ".mtm",
            ".nst",
            ".okt",
            ".plm",
            ".ppm",
            ".psm",
            ".pt36",
            ".ptm",
            ".s3m",
            ".sfx",
            ".sfx2",
            ".stk",
            ".stm",
            ".ult",
            ".umx",
            ".webm",  # 수동으로 추가
            ".wow",
            ".xm",
            ".xpk",
            ".lvf",
            ".m4v",
            ".mkv",
            ".mk3d",
            ".mka",
            ".mks",
            ".mjpg",
            ".mjpeg",
            ".mpo",
            ".j2k",
            ".mlp",
            ".mov",
            ".mp4",
            ".m4a",
            ".3gp",
            ".3g2",
            ".mj2",
            ".mp2",
            ".mp3",
            ".m2a",
            ".mpa",
            ".mpc",
            ".mjpg",
            ".mpl2",
            ".sub",
            ".msf",
            ".mtaf",
            ".ul",
            ".musx",
            ".mvi",
            ".mxg",
            ".v",
            ".nist",
            ".sph",
            ".nut",
            ".ogg",
            ".oma",
            ".omg",
            ".aa3",
            ".pjs",
            ".pvf",
            ".yuv",
            ".cif",
            ".qcif",
            ".rgb",
            ".rt",
            ".rsd",
            ".rso",
            ".sw",
            ".sb",
            ".smi",
            ".sami",
            ".sbg",
            ".scc",
            ".sdr2",
            ".sds",
            ".sdx",
            ".shn",
            ".vb",
            ".son",
            ".sln",
            ".mjpg",
            ".stl",
            ".sub",
            ".sup",
            ".svag",
            ".tak",
            ".thd",
            ".tta",
            ".ans",
            ".art",
            ".asc",
            ".diz",
            ".ice",
            ".nfo",
            ".vt",
            ".uw",
            ".ub",
            ".v210",
            ".yuv10",
            ".vag",
            ".vc1",
            ".viv",
            ".idx",
            ".vpk",
            ".txt",
            ".vqf",
            ".vql",
            ".vqe",
            ".vtt",
            ".wsd",
            ".xmv",
            ".xvag",
            ".yop",
            ".y4m",
        ]
    )
)
