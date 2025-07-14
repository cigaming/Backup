
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
            .astro-box {{
                padding: 10px;
                font-size: 24px;
            }}
        </style>
    </head>
    <body>
        <div class="astro-box">
            <strong>Astronomy Data Unavailable</strong><br>
            <em>Visibility set to False.</em>
        </div>
    </body>
    </html>
    """
    with open(output_path, 'w') as file:
        file.write(html_content)

def main():
    input_path = 'astronomy.json'
    output_path = 'astronomy.html'

    while True:
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
                if data.get('visible', False):
                    create_html(data, output_path)
                else:
                    create_html({"visible": False}, output_path)
                print("Updated Astronomy HTML at", time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print("Error updating Astronomy HTML:", e)

        time.sleep(300)

if __name__ == "__main__":
    main()
