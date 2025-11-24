from setuptools import setup, find_packages

setup(
    name="yt-dlp-simple-downloader",
    version="1.0.0",
    description="A simple GUI downloader for yt-dlp",
    author="Odudins",
    author_email="",
    url="https://github.com/rj-sensei/yt-dlp-simple-downloader",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "PyQt5>=5.15.0",
        "requests>=2.25.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "yt-dlp-downloader=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Video",
    ],
)
