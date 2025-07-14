
import json
import time
from datetime import datetime

def create_html(data, output_path):
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
            .state-box {{
                padding: 10px;
                font-size: 22px;
            }}
        </style>
    </head>
    <body>
        <div class="state-box">
            <strong>Current Display:</strong> {data['current_display'].capitalize()}<br>
            <strong>Mode:</strong> {data['current_mode'].capitalize()}<br>
            <strong>Current City:</strong> {data['current_city']}<br>
            <strong>Warnings in Cycle:</strong> {data['warnings_shown_in_cycle']}<br>
            <strong>Total Active Warnings:</strong> {len(data['active_warnings'])}<br>
            <em>Last Action: {datetime.fromtimestamp(data['last_action_timestamp']).strftime("%Y-%m-%d %H:%M:%S")}</em>
        </div>
    </body>
    </html>
    """
    with open(output_path, 'w') as file:
        file.write(html_content)

def main():
    input_path = 'weatherwise_state.json'
    output_path = 'weatherwise_state.html'

    while True:
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
                create_html(data, output_path)
                print("Updated WeatherWise State HTML at", time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print("Error updating WeatherWise State HTML:", e)

        time.sleep(300)

if __name__ == "__main__":
    main()
