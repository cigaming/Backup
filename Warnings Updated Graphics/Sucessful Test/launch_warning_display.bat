
@echo off
cd /d "%~dp0"
start "" python fetch_nws_warnings_live.py
start "" python warning_data_to_html.py
pause
