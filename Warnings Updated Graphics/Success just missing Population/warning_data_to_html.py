import requests
import time
from datetime import datetime
import pytz

# Sample county population data — add more as needed
county_population = {
    "Chippewa, MN": 11600,
    "Lac qui Parle, MN": 6600,
    "Yellow Medicine, MN": 9800,
    "Cook, IL": 5150000,
    "Jefferson, AL": 655000,
    "Robeson, NC": 116000,
    "Shelby, TN": 936000,
    "Maricopa, AZ": 4485000,
    "Los Angeles, CA": 10040000,
    "Harris, TX": 4780000
}

def get_total_population(area_desc):
    counties = [c.strip() for c in area_desc.split(";")]
    total = 0
    for c in counties:
        if c in county_population:
            total += county_population[c]
    return total if total > 0 else None

def get_warning_icon(warning_type):
    icons = {
        "TORNADO": "🌪",
        "SEVERE THUNDERSTORM": "⚡",
        "FLASH FLOOD": "🌊",
        "FLOOD WARNING": "🌊",
        "FLOOD ADVISORY": "💧",
        "AREAL FLOOD": "💧",
        "DENSE FOG": "🌫",
        "HIGH WIND": "🌬",
        "HEAT": "🔥",
        "WINTER": "❄️",
        "SNOW": "❄️",
        "ICE STORM": "❄️",
        "FREEZE": "🧊",
        "FROST": "🧊",
        "SMALL CRAFT": "⛵",
        "GALE": "⛵",
        "LOCAL AREA EMERGENCY": "🚨",
        "SHELTER": "🚨"
    }
    for key, emoji in icons.items():
        if key in warning_type.upper():
            return emoji
    return "🚨"

def get_color_scheme(warning_type):
    warning_type = warning_type.upper()
    if "TORNADO" in warning_type:
        return ("#8B0000", "#FF0000")
    elif "SEVERE THUNDERSTORM" in warning_type:
        return ("#CCCC00", "#FFFF00")
    elif "FLASH FLOOD" in warning_type or "FLOOD WARNING" in warning_type:
        return ("#006400", "#00CC66")
    elif "FLOOD ADVISORY" in warning_type or "AREAL FLOOD" in warning_type:
        return ("#004D40", "#4DB6AC")
    elif "HIGH WIND" in warning_type:
        return ("#2C3E50", "#5DADE2")
    elif "DENSE FOG" in warning_type:
        return ("#37474F", "#B0BEC5")
    elif "HEAT" in warning_type:
        return ("#B22222", "#FFCCCC")
    elif "WINTER" in warning_type or "SNOW" in warning_type or "ICE STORM" in warning_type:
        return ("#1C2331", "#90CAF9")
    elif "FREEZE" in warning_type or "FROST" in warning_type:
        return ("#0D47A1", "#B3E5FC")
    elif "SMALL CRAFT" in warning_type or "GALE" in warning_type:
        return ("#00008B", "#1E90FF")
    elif "LOCAL AREA EMERGENCY" in warning_type or "SHELTER" in warning_type:
        return ("#000000", "#FF0000")
    else:
        return ("#1c1c1c", "#f4a300")

def convert_to_chicago_time(expires_iso):
    try:
        utc_time = datetime.fromisoformat(expires_iso.replace("Z", "+00:00"))
        chicago_time = utc_time.astimezone(pytz.timezone("America/Chicago"))
        return chicago_time.strftime("%B %d, %Y at %-I:%M %p CT")
    except:
        return expires_iso

def create_html(data, output_path):
    emoji = get_warning_icon(data['type'])
    damage_threat = data.get('damageThreat', "UNKNOWN").upper()
    source = data.get('source', "NWS")
    hail = data.get('hail', "N/A")
    wind = data.get('wind', "N/A")
    expires_fmt = convert_to_chicago_time(data.get("expires", "N/A"))
    dark_color, light_color = get_color_scheme(data['type'])
    population = get_total_population(data['area'])

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="60">
        <link href="https://fonts.googleapis.com/css2?family=Anton&display=swap" rel="stylesheet">
        <style>
            @keyframes pulse-bg {{
                0%   {{ background-color: {dark_color}; }}
                50%  {{ background-color: {light_color}; }}
                100% {{ background-color: {dark_color}; }}
            }}
            @keyframes pulse-title {{
                0%   {{ background-color: #000000; }}
                50%  {{ background-color: #2C2C2C; }}
                100% {{ background-color: #000000; }}
            }}
            body {{
                font-family: 'Anton', sans-serif;
                background-color: transparent;
                color: white;
                margin: 0;
                padding: 0;
            }}
            .container {{
                width: 540px;
                margin: 10px auto;
                box-shadow: 0 0 15px rgba(0,0,0,0.6);
            }}
            .title {{
                animation: pulse-title 2s infinite;
                padding: 14px;
                font-size: 30px;
                text-transform: uppercase;
                text-shadow: 2px 2px 4px black;
                color: white;
                text-align: center;
            }}
            .row {{
                animation: pulse-bg 2s infinite;
                padding: 8px 14px;
                font-size: 20px;
                color: black;
                border-bottom: 2px solid #000;
                text-shadow: 1px 1px 2px rgba(255,255,255,0.3);
            }}
            .row:last-child {{
                background-color: #d68e00;
                color: white;
                font-weight: bold;
                text-shadow: 2px 2px 4px black;
                animation: none;
            }}
            .highlight {{
                color: #FFEB3B;
                text-shadow: 1px 1px 2px #000;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="title">{data['type']} {emoji}</div>
            <div class="row">EXPIRES: {expires_fmt}</div>
            <div class="row">AREAS: {data['area']}</div>
            <div class="row">SOURCE: {source}</div>
            <div class="row">MAX HAIL: {hail}</div>
            <div class="row">MAX WIND: {wind}</div>
            <div class="row">DAMAGE THREAT: <span class="highlight">{damage_threat}</span></div>
            <div class="row">POPULATION IMPACTED: <span class="highlight">{f"~{population:,}" if population else "Unknown"}</span></div>
        </div>
    </body>
    </html>
    """
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(html_content)

def fetch_nws_alert():
    url = "https://api.weather.gov/alerts/active"
    headers = {"User-Agent": "WeatherWiseBot/1.0 (your_email@example.com)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        alerts = response.json().get("features", [])
        for alert in alerts:
            props = alert.get("properties", {})
            if props.get("status") == "Actual":
                return {
                    "type": props.get("event", "N/A"),
                    "expires": props.get("expires", "N/A"),
                    "area": ";".join(props.get("areaDesc", "").split(",")),
                    "source": props.get("senderName", "NWS"),
                    "hail": props.get("hailSize", "N/A"),
                    "wind": props.get("windGust", "N/A"),
                    "damageThreat": props.get("severity", "UNKNOWN"),
                }
    except Exception as e:
        print("Fetch error:", e)
    return None

def main():
    output_path = "warning_data.html"
    while True:
        data = fetch_nws_alert()
        if data:
            create_html(data, output_path)
            print(f"✅ Updated: {data['type']}")
        else:
            print("⚠️ No active alert or failed to fetch.")
        time.sleep(60)

if __name__ == "__main__":
    main()
