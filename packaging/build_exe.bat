@echo off
REM =====================================================
REM  Crée "Streamlink Launcher.exe" (un seul fichier, sans console)
REM  Prérequis : Python 3.10+ pour Windows (python.org), avec Tcl/Tk (coché par défaut)
REM  Usage : double-clic, ou depuis ce dossier : build_exe.bat
REM  (sur GitHub Actions, la variable CI supprime les pauses)
REM =====================================================
cd /d "%~dp0\.."

where py >nul 2>nul && (set PY=py -3) || (set PY=python)

REM Version de PyInstaller figee dans requirements-build.txt.
REM Sur GitHub Actions, BUILD_BOOTLOADER=1 recompile le chargeur de PyInstaller depuis ses sources :
REM le chargeur precompile est partage par des milliers de programmes (dont des malveillants),
REM ce qui provoque des faux positifs antivirus. Il faut alors Visual Studio Build Tools (C++).
echo Installation de PyInstaller...
if "%BUILD_BOOTLOADER%"=="1" (
  set PYINSTALLER_COMPILE_BOOTLOADER=1
  %PY% -m pip install --no-binary pyinstaller -r packaging\requirements-build.txt || goto :erreur
) else (
  %PY% -m pip install -r packaging\requirements-build.txt || goto :erreur
)

echo Compilation...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --noupx ^
  --name "Streamlink Launcher" ^
  --icon "launcher\app.ico" ^
  --version-file "packaging\version_info.txt" ^
  --add-data "lang;lang" ^
  --add-data "launcher\app.ico;launcher" ^
  --exclude-module unittest --exclude-module doctest --exclude-module pydoc_data --exclude-module lib2to3 ^
  slink_launcher.py || goto :erreur

echo.
echo Termine : dist\Streamlink Launcher.exe
echo Copie-le dans ton dossier Streamlink (a cote du dossier streams).
if not defined CI pause
exit /b 0

:erreur
echo.
echo La compilation a echoue (voir les messages ci-dessus).
if not defined CI pause
exit /b 1
