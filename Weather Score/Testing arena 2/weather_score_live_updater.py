
import json
import time
from pathlib import Path
from datetime import datetime

def generate_html(score_data):
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <title>Weather Activity Score</title>
    <style>
        body {{
            background-color: #111;
            color: white;
            font-family: Arial, sans-serif;
            padding: 20px;
        }}
        .score {{
            font-size: 48px;
            font-weight: bold;
            color: #00ffcc;
        }}
        .section {{
            margin-bottom: 20px;
        }}
        .label {{
            font-size: 20px;
            font-weight: bold;
            color: #ffcc00;
        }}
        .value {{
            font-size: 24px;
            color: #ffffff;
        }}
    </style>
</head>
<body>
    <h1>⚡ Weather Activity Score</h1>
    <div class="section">
        <span class="label">Total Score:</span>
        <div class="score">{{score_data['total_score']}}</div>
    </div>
    <div class="section">
        <span class="label">Severity Counts:</span>
        <ul>
            {"".join(f"<li class='value'>{{k}}: {{v}}</li>" for k, v in score_data['severity_counts'].items())}
        </ul>
    </div>
    <div class="section">
        <span class="label">Type Counts:</span>
        <ul>
            {"".join(f"<li class='value'>{{k}}: {{v}}</li>" for k, v in score_data['type_counts'].items())}
        </ul>
    </div>
    <div class="section">
        <span class="label">PDS Count:</span>
        <span class="value">{{score_data['pds_count']}}</span>
    </div>
    <div class="section">
        <span class="label">Timestamp:</span>
        <span class="value">{{score_data['timestamp']}}</span>
    </div>
</body>
</html>"""
    return html_content

json_path = Path("weather_score.json")
html_path = Path("weather_score.html")

print("Real-time weather score updater is running...")

while True:
    try:
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            html_output = generate_html(data)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_output)
        else:
            print("weather_score.json not found.")
        time.sleep(30)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(30)
