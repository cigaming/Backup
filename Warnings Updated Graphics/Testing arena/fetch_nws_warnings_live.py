
import requests
import json
from datetime import datetime

def fetch_and_save_latest_warning():
    url = "https://api.weather.gov/alerts/active"
    headers = {
        "User-Agent": "WeatherWiseBot (admin@example.com)"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch data: {response.status_code}")
        return

    alerts = response.json().get("features", [])
    if not alerts:
        print("No alerts found.")
        return

    warnings = [a for a in alerts if "WARNING" in a["properties"]["event"].upper()]
    if not warnings:
        print("No warnings found.")
        return

    latest = sorted(warnings, key=lambda x: x["properties"]["onset"] or "", reverse=True)[0]
    prop = latest["properties"]

    data = {
        "visible": True,
        "type": prop["event"].upper(),
        "area": prop.get("areaDesc", "N/A"),
        "population": "N/A",
        "severity": prop.get("severity", "Unknown"),
        "certainty": prop.get("certainty", "Unknown"),
        "wind": "N/A",
        "hail": None,
        "expires": prop.get("expires", "N/A"),
        "isPDS": False
    }

    with open("warning_data.json", "w") as f:
        json.dump(data, f, indent=4)
    print("✅ Updated warning_data.json")

if __name__ == "__main__":
    fetch_and_save_latest_warning()
