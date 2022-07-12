# from glob import glob
# from posixpath import basename, splitext
import setuptools

required_packages = [
    "tqdm==4.64.0",
    "ffmpeg-python==0.2.0",
    "colorlog==6.6.0",
    "pyyaml==6.0",
]

setuptools.setup(
    name="py-media-compressor",
    version="0.0.1",
    author="cardroid",
    author_email="carbonsindh@gmail.com",
    description="Media compression encoder with ffmpeg Python wrapper",
    install_requires=required_packages,
    license="MIT",
    packages=setuptools.find_packages(where="py_media_compressor"),
    package_dir={"": "py_media_compressor"},
    python_requires=">=3.8",
    include_package_data=True,
    entry_points={"console_scripts": ["encode=encoder:main"]},
)
