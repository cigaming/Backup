
@echo off
cd /d "%~dp0"
echo Launching Air Quality HTML auto-updater...
python air_quality_to_html.py
pause
