@echo off
REM =====================================================
REM  Crée "Streamlink Launcher.exe" (un seul fichier, sans console)
REM  Prérequis : Python 3.10+ pour Windows (python.org), avec Tcl/Tk (coché par défaut)
REM  Usage : double-clic, ou depuis ce dossier : build_exe.bat
REM  (sur GitHub Actions, la variable CI supprime les pauses)
REM =====================================================
cd /d "%~dp0\.."

where py >nul 2>nul && (set PY=py -3) || (set PY=python)

echo Installation / mise a jour de PyInstaller...
%PY% -m pip install --upgrade pyinstaller || goto :erreur

echo Compilation...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
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
