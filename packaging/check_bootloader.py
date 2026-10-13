"""Vérifie (sur GitHub Actions) que le chargeur de PyInstaller a bien été recompilé sur place.

Compare runw.exe installé avec celui du paquet précompilé publié sur PyPI : s'ils sont identiques,
la recompilation n'a pas eu lieu et l'exe garderait le chargeur qui déclenche les faux positifs.
"""
import glob
import hashlib
import os
import subprocess
import sys
import tempfile
import traceback
import zipfile

NAME = "PyInstaller/bootloader/Windows-64bit-intel/runw.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    import PyInstaller
    installed = os.path.join(os.path.dirname(PyInstaller.__file__), "bootloader", "Windows-64bit-intel", "runw.exe")
    local = hashlib.sha256(open(installed, "rb").read()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "pip", "download", "--quiet", "--no-deps", "--only-binary", ":all:",
                        "-r", os.path.join(ROOT, "packaging", "requirements-build.txt"), "-d", tmp], check=True)
        wheel = glob.glob(os.path.join(tmp, "pyinstaller-*.whl"))[0]
        with zipfile.ZipFile(wheel) as z:
            prebuilt = hashlib.sha256(z.read(NAME)).hexdigest()
    print(f"::notice::PyInstaller {PyInstaller.__version__} bootloader runw.exe: "
          f"local {local[:16]}, prebuilt {prebuilt[:16]}")
    if local == prebuilt:
        print("::error::The prebuilt PyInstaller bootloader was used (it was not compiled from source)")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"::error::check_bootloader: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
