
@echo off
cd /d "%~dp0"
echo Launching Weather Score HTML auto-updater...
python weather_score_to_html.py
pause
