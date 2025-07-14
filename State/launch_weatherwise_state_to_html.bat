
@echo off
cd /d "%~dp0"
echo Launching WeatherWise State HTML auto-updater...
python weatherwise_state_to_html.py
pause
