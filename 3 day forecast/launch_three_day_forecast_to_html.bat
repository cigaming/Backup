
@echo off
cd /d "%~dp0"
echo Launching 3-Day Forecast HTML auto-updater...
python three_day_forecast_to_html.py
pause
