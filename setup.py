from setuptools import setup

setup(
    name="yt-dlp-simple-downloader",
    version="1.2.0",
    description="Responsive Windows GUI downloader for yt-dlp",
    author="Odudins",
    url="https://github.com/rj-sensei/yt-dlp-simple-downloader",
    license="MIT",
    py_modules=["main", "downloader_core", "downloader_workers", "style"],
    install_requires=["PyQt5==5.15.11", "requests==2.32.5"],
    python_requires=">=3.10",
    entry_points={"gui_scripts": ["yt-dlp-downloader=main:main"]},
)
