
import json
import time
from datetime import datetime

def create_html(data, output_path):
    timestamp = datetime.fromisoformat(data['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
    html_content = f"""
    <html>
    <head>
        <meta http-equiv="refresh" content="300">
        <style>
            body {{
                font-family: Arial, sans-serif;
                color: white;
                background-color: transparent;
            }}
            .score-box {{
                padding: 10px;
                font-size: 24px;
            }}
        </style>
    </head>
    <body>
        <div class="score-box">
            <strong>Total Weather Score:</strong> {data['total_score']}<br>
            <strong>Extreme:</strong> {data['severity_counts']['Extreme']} |
            <strong>Severe:</strong> {data['severity_counts']['Severe']} |
            <strong>Moderate:</strong> {data['severity_counts']['Moderate']} |
            <strong>Minor:</strong> {data['severity_counts']['Minor']} |
            <strong>Unknown:</strong> {data['severity_counts']['Unknown']}<br>
            <strong>Severe Thunderstorm Warnings:</strong> {data['type_counts'].get('Severe Thunderstorm Warning', 0)}<br>
            <strong>PDS Count:</strong> {data['pds_count']}<br>
            <em>Last Updated: {timestamp}</em>
        </div>
    </body>
    </html>
    """
    with open(output_path, 'w') as file:
        file.write(html_content)

def main():
    input_path = 'weather_score.json'
    output_path = 'weather_score.html'

    while True:
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
                create_html(data, output_path)
                print("Updated Weather Score HTML at", time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print("Error updating Weather Score HTML:", e)

        time.sleep(300)

if __name__ == "__main__":
    main()
