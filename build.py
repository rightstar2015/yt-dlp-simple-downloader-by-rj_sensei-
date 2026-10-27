"""Build the Windows GUI without installing packages or collecting unused Qt modules."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--distpath", default=str(project / "dist"))
    parser.add_argument("--workpath", default=str(project / "build"))
    parser.add_argument("--name", default="yt-dlp-downloader")
    args = parser.parse_args()
    if importlib.util.find_spec("PyInstaller") is None:
        print("缺少打包依賴，請先執行：python -m pip install -r requirements-build.txt")
        return 1
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--noupx",
               "--name", args.name, "--distpath", args.distpath, "--workpath", args.workpath,
               "--specpath", str(project), str(project / "main.py")]
    result = subprocess.run(command, cwd=project)
    if result.returncode:
        return result.returncode
    exe = Path(args.distpath) / (args.name + ".exe")
    print(f"打包完成：{exe}（{exe.stat().st_size / (1024 * 1024):.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
