@echo off
REM Doble clic para arrancar el programa de la tienda en Windows.
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Falta Python. Instalalo desde https://www.python.org/downloads/ y marca "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Preparando por primera vez, tarda un minuto...
  py -3 -m venv .venv || goto error
  ".venv\Scripts\python.exe" -m pip install -q --upgrade pip || goto error
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto error
)
".venv\Scripts\python.exe" iniciar.py %*
pause
exit /b 0
:error
echo No se pudo preparar. Revisa tu internet y vuelve a intentar.
rmdir /s /q .venv
pause
exit /b 1
