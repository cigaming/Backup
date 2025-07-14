
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
            .aq-box {{
                padding: 10px;
                font-size: 24px;
            }}
        </style>
    </head>
    <body>
        <div class="aq-box">
            <strong>Air Quality Data Unavailable</strong><br>
            <em>Visibility set to False.</em>
        </div>
    </body>
    </html>
    """
    with open(output_path, 'w') as file:
        file.write(html_content)

def main():
    input_path = 'air_quality.json'
    output_path = 'air_quality.html'

    while True:
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
                if data.get('visible', False):
                    # If future expansion includes AQ data, update this part
                    create_html(data, output_path)
                else:
                    create_html({"visible": False}, output_path)
                print("Updated Air Quality HTML at", time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print("Error updating Air Quality HTML:", e)

        time.sleep(300)

if __name__ == "__main__":
    main()
