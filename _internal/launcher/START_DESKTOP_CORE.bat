@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..\..") do set "APPROOT=%%~fI"
cd /d "%APPROOT%" || exit /b 16

set "LOGDIR=%APPROOT%\runtime_data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
set "BOOTLOG=%LOGDIR%\desktop_bootstrap.log"

rem ---------------------------------------------------------------------------
rem FAST PATH: once a venv has passed the dependency check, start it directly.
rem This avoids launching py.exe several times and importing pandas/paramiko/etc
rem on every click.  A new ready marker is used whenever bootstrap requirements
rem change, so an upgraded bundle performs one validation then becomes instant.
rem ---------------------------------------------------------------------------
if defined LOCALAPPDATA (
  set "VENV_ROOT=%LOCALAPPDATA%\NetworkAutomation\venvs"
) else (
  set "VENV_ROOT=%TEMP%\NetworkAutomation\venvs"
)
set "READY_MARKER=.na_ready_70393"
set "CURRENT_VENV_FILE=%VENV_ROOT%\current-7.0.3.txt"
set "VENV_DIR="

if exist "%CURRENT_VENV_FILE%" (
  set /p "VENV_DIR="<"%CURRENT_VENV_FILE%"
  if defined VENV_DIR if exist "%VENV_DIR%\Scripts\pythonw.exe" if exist "%VENV_DIR%\%READY_MARKER%" goto RUNAPP_FAST
)

if not exist "%VENV_ROOT%" mkdir "%VENV_ROOT%" >nul 2>nul
if not exist "%VENV_ROOT%" (
  echo [%date% %time%] Cannot create venv root: "%VENV_ROOT%">>"%BOOTLOG%"
  exit /b 15
)

echo.>>"%BOOTLOG%"
echo [%date% %time%] ===== NetworkAutomation Desktop 7.0.3 bootstrap =====>>"%BOOTLOG%"
echo [%date% %time%] App root: "%APPROOT%">>"%BOOTLOG%"

rem Find a supported CPython only when no validated venv is available.
set "PY_EXE="
set "PY_ARGS="
set "PY_TAG="

py -3.13 -c "import sys" >nul 2>nul && (set "PY_EXE=py"&set "PY_ARGS=-3.13"&set "PY_TAG=313"&goto PYFOUND)
py -3.12 -c "import sys" >nul 2>nul && (set "PY_EXE=py"&set "PY_ARGS=-3.12"&set "PY_TAG=312"&goto PYFOUND)
py -3.11 -c "import sys" >nul 2>nul && (set "PY_EXE=py"&set "PY_ARGS=-3.11"&set "PY_TAG=311"&goto PYFOUND)

if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (set "PY_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"&set "PY_TAG=313"&goto PYFOUND)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"&set "PY_TAG=312"&goto PYFOUND)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (set "PY_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"&set "PY_TAG=311"&goto PYFOUND)
if exist "%ProgramFiles%\Python313\python.exe" (set "PY_EXE=%ProgramFiles%\Python313\python.exe"&set "PY_TAG=313"&goto PYFOUND)
if exist "%ProgramFiles%\Python312\python.exe" (set "PY_EXE=%ProgramFiles%\Python312\python.exe"&set "PY_TAG=312"&goto PYFOUND)
if exist "%ProgramFiles%\Python311\python.exe" (set "PY_EXE=%ProgramFiles%\Python311\python.exe"&set "PY_TAG=311"&goto PYFOUND)

python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_EXE=python"
  for /f "usebackq delims=" %%V in (`python -c "import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))"`) do set "PY_TAG=%%V"
)

:PYFOUND
if not defined PY_EXE (
  echo [%date% %time%] Compatible Python 3.11-3.13 not found.>>"%BOOTLOG%"
  exit /b 11
)
if not defined PY_TAG set "PY_TAG=312"

echo [%date% %time%] Using Python: "%PY_EXE%" %PY_ARGS% ^(tag=%PY_TAG%^)>>"%BOOTLOG%"

set "VENV_DIR=%VENV_ROOT%\7.0.3-py%PY_TAG%"
if not exist "%VENV_DIR%" goto CREATEVENV

if exist "%VENV_DIR%\Scripts\pythonw.exe" (
  "%VENV_DIR%\Scripts\python.exe" -c "import fastapi,uvicorn,webview,pandas,openpyxl,paramiko,cryptography,pysnmp,pydantic,argon2,psutil" >nul 2>nul && goto MARKREADY
)

echo [%date% %time%] Existing versioned environment is incomplete; keeping it untouched and creating a repair environment.>>"%BOOTLOG%"
set "VENV_DIR=%VENV_ROOT%\7.0.3-py%PY_TAG%-repair-%RANDOM%-%RANDOM%"
if exist "%VENV_DIR%" set "VENV_DIR=%VENV_ROOT%\7.0.3-py%PY_TAG%-repair-%RANDOM%-%RANDOM%-%RANDOM%"

:CREATEVENV
echo [%date% %time%] Creating venv: "%VENV_DIR%">>"%BOOTLOG%"
"%PY_EXE%" %PY_ARGS% -m venv "%VENV_DIR%" >>"%BOOTLOG%" 2>&1 || exit /b 12
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >>"%BOOTLOG%" 2>&1 || exit /b 13
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%APPROOT%\requirements-lock.txt" >>"%BOOTLOG%" 2>&1 || exit /b 14
"%VENV_DIR%\Scripts\python.exe" -c "import fastapi,uvicorn,webview,pandas,openpyxl,paramiko,cryptography,pysnmp,pydantic,argon2,psutil" >>"%BOOTLOG%" 2>&1 || exit /b 14

:MARKREADY
>"%VENV_DIR%\%READY_MARKER%" echo ready
>"%CURRENT_VENV_FILE%" echo %VENV_DIR%
echo [%date% %time%] Validated fast-start environment: "%VENV_DIR%">>"%BOOTLOG%"

goto RUNAPP

:RUNAPP_FAST
rem Keep warm starts almost silent: no Python discovery and no dependency imports.
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
goto RUNAPP

:RUNAPP
echo [%date% %time%] Starting NetworkAutomation Desktop 7.0.3 with "%VENV_DIR%"...>>"%BOOTLOG%"
"%VENV_DIR%\Scripts\pythonw.exe" "%APPROOT%\desktop_launcher.py" >>"%BOOTLOG%" 2>&1
set "APP_RC=%ERRORLEVEL%"
echo [%date% %time%] Desktop process exited with code %APP_RC%.>>"%BOOTLOG%"
exit /b %APP_RC%
