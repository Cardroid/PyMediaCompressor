# from glob import glob
# from posixpath import basename, splitext
import setuptools

required_packages = [
    "tqdm==4.64.0",
    "ffmpeg-python==0.2.0",
    "colorlog==6.6.0",
    "pyyaml==6.0",
    "bitmath==1.3.3.1",
]

setuptools.setup(
    name="py-media-compressor",
    version="1.0.1",
    author="cardroid",
    author_email="carbonsindh@gmail.com",
    description="Media compression encoder with ffmpeg Python wrapper",
    install_requires=required_packages,
    license="MIT",
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    entry_points={"console_scripts": ["encode=py_media_compressor.encoder:main"]},
)
