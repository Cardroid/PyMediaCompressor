from importlib.machinery import SourceFileLoader

import setuptools

version = SourceFileLoader("py_media_compressor.version", "src/py_media_compressor/version.py").load_module().version

with open("README.md", mode="r", encoding="utf-8") as f:
    readme_description = f.read()

required_packages = [
    "tqdm==4.64.0",
    "ffmpeg-python==0.2.0",
    "colorlog==6.6.0",
    "pyyaml==6.0",
    "bitmath==1.3.3.1",
    "psutil==5.9.1",
]

setuptools.setup(
    name="py-media-compressor",
    version=version,
    author="cardroid",
    author_email="carbonsindh@gmail.com",
    description="Media compression encoder with ffmpeg Python wrapper",
    install_requires=required_packages,
    license="MIT",
    long_description=readme_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    entry_points={"console_scripts": ["encode=py_media_compressor.entry.encode:main"]},
)
