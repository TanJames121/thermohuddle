@echo off
title ThermoHuddle App Server
cd /d "%~dp0"
start "" "http://localhost:8422/brooder_tracker.html"
where python >nul 2>nul
if %errorlevel%==0 (
  python -m http.server 8422
) else (
  py -m http.server 8422
)
