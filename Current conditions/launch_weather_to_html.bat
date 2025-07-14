
@echo off
cd /d "%~dp0"
echo Launching Weather to HTML auto-updater...
python weather_to_html.py
pause
