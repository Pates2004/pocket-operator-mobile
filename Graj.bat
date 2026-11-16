@echo off
setlocal
title Pocket Operator mobile v16.0
cd /d "%~dp0"

if exist "Installfiles\PocketOperator-mobile\PocketOperator-mobile.exe" (
    start "" "Installfiles\PocketOperator-mobile\PocketOperator-mobile.exe"
    goto end
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1"
if errorlevel 1 pause

:end
endlocal
