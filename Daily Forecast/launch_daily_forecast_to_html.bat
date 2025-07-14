
@echo off
cd /d "%~dp0"
echo Launching Daily Forecast HTML auto-updater...
python daily_forecast_to_html.py
pause
