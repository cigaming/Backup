
import requests
import json
import time
from datetime import datetime

def fetch_nws_alerts():
    url = "https://api.weather.gov/alerts/active"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()["features"]
    except Exception as e:
        print(f"Error fetching NWS alerts: {e}")
        return []

def calculate_score(alerts):
    severity_counts = {
        "Extreme": 0,
        "Severe": 0,
        "Moderate": 0,
        "Minor": 0,
        "Unknown": 0
    }
    type_counts = {}
    total_score = 0
    pds_count = 0

    for alert in alerts:
        props = alert["properties"]
        severity = props.get("severity", "Unknown")
        event_type = props.get("event", "Unknown")
        is_pds = "PDS" in props.get("headline", "")

        # Count severities
        if severity in severity_counts:
            severity_counts[severity] += 1
        else:
            severity_counts["Unknown"] += 1

        # Count types
        type_counts[event_type] = type_counts.get(event_type, 0) + 1

        # Add to score
        if severity == "Extreme":
            total_score += 20
        elif severity == "Severe":
            total_score += 10
        elif severity == "Moderate":
            total_score += 5
        elif severity == "Minor":
            total_score += 2
        else:
            total_score += 1

        if is_pds:
            pds_count += 1
            total_score += 15

    return {
        "total_score": total_score,
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "pds_count": pds_count,
        "timestamp": datetime.now().isoformat()
    }

def main():
    while True:
        alerts = fetch_nws_alerts()
        score_data = calculate_score(alerts)
        with open("weather_score.json", "w") as f:
            json.dump(score_data, f, indent=4)
        print("Updated weather_score.json at", score_data["timestamp"])
        time.sleep(60)

if __name__ == "__main__":
    main()
