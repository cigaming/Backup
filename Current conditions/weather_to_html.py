
import json
import time

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
            .weather-box {{
                padding: 10px;
                font-size: 24px;
            }}
        </style>
    </head>
    <body>
        <div class="weather-box">
            <strong>Location:</strong> {data['location']}<br>
            <strong>Temp:</strong> {data['temperature']}°F (Feels like {data['feelsLike']}°F)<br>
            <strong>Condition:</strong> {data['description']}<br>
            <strong>Wind:</strong> {data['wind']} (Gusts: {data['windGust']})<br>
            <strong>Humidity:</strong> {data['humidity']}<br>
            <strong>Dewpoint:</strong> {data['dewpoint']}°F<br>
            <strong>Pressure:</strong> {data['pressure']}<br>
            <strong>Visibility:</strong> {data['visibility']}<br>
            <strong>UV Index:</strong> {data['uvIndex']}<br>
            <em>Data from {data['dataSource']}</em>
        </div>
    </body>
    </html>
    """
    with open(output_path, 'w') as file:
        file.write(html_content)

def main():
    input_path = 'current_conditions.json'
    output_path = 'output.html'

    while True:
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
                if data.get('visible', True):
                    create_html(data, output_path)
                    print("Updated HTML at", time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print("Error updating HTML:", e)

        time.sleep(300)  # wait 5 minutes

if __name__ == "__main__":
    main()
