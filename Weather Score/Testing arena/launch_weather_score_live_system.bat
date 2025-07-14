@echo off
cd /d "%~dp0"
start python generate_live_weather_score.py
start python weather_score_to_html.py
pause
