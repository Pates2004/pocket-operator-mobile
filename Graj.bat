@echo off
setlocal
title Pocket Operator mobile v15.0
cd /d "%~dp0"

echo Uruchamianie Pocket Operator mobile v15.0...
py -3 run.py
if %ERRORLEVEL% EQU 0 goto end

python run.py
if %ERRORLEVEL% EQU 0 goto end

echo.
echo BLAD: Nie udalo sie uruchomic programu.
echo Zainstaluj Python 3.10 lub nowszy i wykonaj:
echo python -m pip install -r requirements.txt
pause

:end
endlocal
