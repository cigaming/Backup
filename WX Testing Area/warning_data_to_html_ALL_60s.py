
import json
import time

def get_warning_icon(warning_type):
    key = warning_type.upper()
    if "TORNADO" in key:
        return "🌪", "icons/tornado.png"
    elif "SEVERE" in key:
        return "⚡", "icons/tstorm.png"
    elif "FLOOD" in key:
        return "🌊", "icons/flood.png"
    elif "HAIL" in key:
        return "🧊", "icons/hail.png"
    elif "FOG" in key:
        return "🌫", "icons/fog.png"
    elif "WIND" in key:
        return "💨", "icons/wind.png"
    elif "HEAT" in key:
        return "🥵", "icons/heat.png"
    elif "WINTER" in key:
        return "❄️", "icons/winter.png"
    elif "FIRE" in key:
        return "🔥", "icons/fire.png"
    elif "HURRICANE" in key:
        return "🌀", "icons/hurricane.png"
    else:
        return "🚨", "icons/alert.png"

def get_flash_class(warning_type):
    key = warning_type.upper()
    if "TORNADO" in key:
        return "flash-red"
    elif "SEVERE" in key:
        return "flash-yellow"
    elif "FLOOD" in key:
        return "flash-green"
    elif "FOG" in key:
        return "flash-yellow"
    elif "WIND" in key:
        return "flash-yellow"
    elif "HEAT" in key:
        return "flash-red"
    elif "WINTER" in key:
        return "flash-green"
    else:
        return "flash-yellow"

def get_threat_class(warning_type):
    key = warning_type.upper()
    if "TORNADO" in key:
        return "threat-red"
    elif "SEVERE" in key:
        return "threat-yellow"
    elif "FLOOD" in key or "WINTER" in key:
        return "threat-green"
    else:
        return "threat-yellow"

def create_html(data, output_path):
    hail = data['hail'] if data['hail'] else "N/A"
    emoji, icon_path = get_warning_icon(data['type'])
    flash_class = get_flash_class(data['type'])
    threat_class = get_threat_class(data['type'])
    severity = data.get('severity', 'MINOR').upper()
    source = "PUBLIC"
    icon_img = f'<img src="{icon_path}" class="icon" alt="icon">' if icon_path else ""

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="300">
        <link href="https://fonts.googleapis.com/css2?family=Anton&display=swap" rel="stylesheet">
        <style>
            @keyframes flash-yellow {{
                0%, 100% {{ background-color: #f4a300; }}
                50% {{ background-color: #ffcc00; }}
            }}
            @keyframes flash-red {{
                0%, 100% {{ background-color: #b30000; }}
                50% {{ background-color: #ff0000; }}
            }}
            @keyframes flash-green {{
                0%, 100% {{ background-color: #1b5e20; }}
                50% {{ background-color: #66bb6a; }}
            }}
            @keyframes threat-yellow {{
                0%, 100% {{ background-color: #ffcc00; color: #000; }}
                50% {{ background-color: #ff9900; color: #000; }}
            }}
            @keyframes threat-red {{
                0%, 100% {{ background-color: #ff0000; color: #000; }}
                50% {{ background-color: #ffffff; color: #000; }}
            }}
            @keyframes threat-green {{
                0%, 100% {{ background-color: #66bb6a; color: #000; }}
                50% {{ background-color: #1b5e20; color: #000; }}
            }}
            body {{
                font-family: 'Anton', sans-serif;
                background-color: transparent;
                margin: 0;
                padding: 0;
                color: white;
                text-shadow: 2px 2px 4px black;
            }}
            .container {{
                width: 540px;
                margin: 10px auto;
                box-shadow: 0 0 15px rgba(0,0,0,0.6);
            }}
            .title {{
                background-color: #1c1c1c;
                padding: 18px;
                font-size: 34px;
                text-transform: uppercase;
                color: white;
                text-shadow: 3px 3px 5px black;
            }}
            .row {{
                padding: 10px 16px;
                font-size: 22px;
                background-color: #f4a300;
                color: black;
                border-bottom: 2px solid #000;
                text-shadow: 2px 2px 3px white;
            }}
            .flash-yellow {{ animation: flash-yellow 1.5s infinite; }}
            .flash-red {{ animation: flash-red 1.5s infinite; }}
            .flash-green {{ animation: flash-green 1.5s infinite; }}
            .threat-yellow {{ animation: threat-yellow 1.5s infinite; }}
            .threat-red {{ animation: threat-red 1.5s infinite; }}
            .threat-green {{ animation: threat-green 1.5s infinite; }}
            .highlight {{
                color: black;
            }}
            .icon {{
                height: 22px;
                vertical-align: middle;
                margin-left: 6px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="title">{data['type']} {emoji} {icon_img}</div>
            <div class="row {flash_class}">EXPIRES: {data['expires']}</div>
            <div class="row {flash_class}">AREAS: {data['area']}</div>
            <div class="row {flash_class}">SOURCE: {source}</div>
            <div class="row {flash_class}">MAX HAIL: {hail}</div>
            <div class="row {flash_class}">MAX WIND: {data['wind']}</div>
            <div class="row {threat_class}">DAMAGE THREAT: <span class="highlight">{severity}</span></div>
        </div>
    </body>
    </html>
    """
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(html_content)
