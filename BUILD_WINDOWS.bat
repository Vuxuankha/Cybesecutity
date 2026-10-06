@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_EXE="
set "PY_ARGS="
py -3.13 -c "import sys" >nul 2>nul && (set "PY_EXE=py"&set "PY_ARGS=-3.13"&goto PYFOUND)
py -3.12 -c "import sys" >nul 2>nul && (set "PY_EXE=py"&set "PY_ARGS=-3.12"&goto PYFOUND)
py -3.11 -c "import sys" >nul 2>nul && (set "PY_EXE=py"&set "PY_ARGS=-3.11"&goto PYFOUND)
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (set "PY_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"&goto PYFOUND)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"&goto PYFOUND)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (set "PY_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"&goto PYFOUND)
python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
if not errorlevel 1 set "PY_EXE=python"

:PYFOUND
if not defined PY_EXE (
  echo Python 3.11, 3.12 or 3.13 was not found.
  exit /b 1
)

if exist .buildvenv rmdir /s /q .buildvenv
"%PY_EXE%" %PY_ARGS% -m venv .buildvenv || exit /b 1
call ".buildvenv\Scripts\activate.bat" || exit /b 1
python -m pip install --upgrade pip || exit /b 1
python -m pip install -r requirements-dev.txt || exit /b 1
python -m compileall -q desktop_launcher.py webapi modules database || exit /b 1
python QA_DESKTOP_GATE.py || exit /b 1
python -m pytest -q || exit /b 1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist release rmdir /s /q release

pyinstaller --noconfirm NetworkAutomationDesktop.spec || exit /b 1

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 was not found. Use the included GitHub Actions workflow to build automatically.
  exit /b 2
)
"%ISCC%" "installer\NetworkAutomation.iss" || exit /b 1
certutil -hashfile "release\NetworkAutomation_Setup_7.0.3.exe" SHA256 > "release\SHA256SUMS.txt"
echo.
echo Build complete: release\NetworkAutomation_Setup_7.0.3.exe
