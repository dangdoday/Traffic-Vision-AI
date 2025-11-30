@echo off
setlocal
rem Launcher to run Traffic-Vision-AI with the prepared Python 3.10 + torch env

rem Project root (one level up from this script)
set ROOT=%~dp0..

rem Micromamba environment location
set MAMBA_ROOT_PREFIX=%ROOT%\.micromamba\root

rem Execute app inside env "tvai"
"%ROOT%\.micromamba\bin\micromamba.exe" run -n tvai python "%~dp0src\main.py" %*
