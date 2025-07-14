
import requests
import time
from datetime import datetime

output_path = "alert_bar_live.html"

alert_colors = {
    "tornado warning": ("#8B0000", "#FF0000"),
    "severe thunderstorm warning": ("#B8860B", "#FFD700"),
    "flash flood warning": ("#006400", "#32CD32"),
    "flood warning": ("#2E8B57", "#66CDAA"),
    "heat advisory": ("#B22222", "#FF6347"),
    "dense fog advisory": ("#2F4F4F", "#B0C4DE"),
    "high wind warning": ("#696969", "#D3D3D3"),
    "high wind watch": ("#778899", "#DCDCDC"),
    "small craft advisory": ("#1E90FF", "#87CEFA"),
    "special weather statement": ("#333333", "#999999"),
    "marine warning": ("#00008B", "#87CEFA"),  # DarkBlue to LightSkyBlue

}

default_dark = "#6A5ACD"
default_light = "#9370DB"

def generate_html(alert_type, locations, threats, dark, light):
    return f'''
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="60">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Anton&display=swap');
        body {{
            margin: 0;
            background-color: transparent;
            font-family: 'Anton', sans-serif;
        }}
        .alert-banner {{
            display: flex;
            flex-direction: column;
            width: 100%;
            color: #e0e0e0;
            font-size: 18px;
            text-shadow: 2px 2px 3px black;
        }}
        .main {{
            display: flex;
            animation: pulse-bg 2s infinite;
        }}
        .left {{
            width: 260px;
            background-color: rgba(0,0,0,0.3);
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 20px;
            font-weight: bold;
            text-transform: uppercase;
            padding: 10px;
            text-align: center;
            border-right: 2px solid white;
            -webkit-text-stroke: 0.5px black;
        }}
        .right {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 6px 14px;
        }}
        .row {{
            margin: 2px 0;
        }}
        .label {{
            font-weight: bold;
            margin-right: 6px;
            color: #FFEB3B;
            text-shadow: 2px 2px 3px black;
        }}
        .color-bar {{
            height: 5px;
            width: 100%;
            animation: pulse-bg 2s infinite;
        }}
        @keyframes pulse-bg {{
            0%   {{ background-color: {dark}; }}
            50%  {{ background-color: {light}; }}
            100% {{ background-color: {dark}; }}
        }}
    </style>
</head>
<body>
    <div class="alert-banner">
        <div class="main">
            <div class="left">{alert_type.upper()}</div>
            <div class="right">
                <div class="row"><span class="label">LOCATIONS:</span> {locations}</div>
                <div class="row"><span class="label">THREATS:</span> {threats}</div>
            </div>
        </div>
        <div class="color-bar"></div>
    </div>
</body>
</html>
'''

def match_alert_color(alert_type):
    lower = alert_type.lower()
    for key in alert_colors:
        if key in lower:
            return alert_colors[key]
    return default_dark, default_light

def fetch_active_alert():
    try:
        r = requests.get("https://api.weather.gov/alerts/active", timeout=10)
        data = r.json()
        if "features" not in data or not data["features"]:
            return None
        alert = data["features"][0]["properties"]
        return {
            "alert_type": alert["event"],
            "locations": alert.get("areaDesc", "N/A").replace(";", " •"),
            "threats": alert.get("description", "No specific threats.").split(".")[0] + "."
        }
    except Exception as e:
        return {
            "alert_type": "NO ACTIVE ALERTS",
            "locations": "All Clear",
            "threats": str(e)
        }

def update_html():
    while True:
        alert = fetch_active_alert()
        alert_type = alert["alert_type"]
        dark, light = match_alert_color(alert_type)

        html = generate_html(alert_type, alert["locations"], alert["threats"], dark, light)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Alert updated: {alert_type}")
        time.sleep(60)

if __name__ == "__main__":
    update_html()
