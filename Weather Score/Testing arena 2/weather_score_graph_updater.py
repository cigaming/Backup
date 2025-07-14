
import json
import time
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import base64
from io import BytesIO

# Define paths
json_path = Path("weather_score.json")
html_output = Path("weather_score_graph_panel.html")
history_csv = Path("weather_score_history.csv")

def load_history():
    if history_csv.exists():
        return pd.read_csv(history_csv, parse_dates=["timestamp"])
    return pd.DataFrame(columns=["timestamp", "score"])

def save_history(df):
    df.to_csv(history_csv, index=False)

def plot_chart(df):
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.plot(df["timestamp"], df["score"], color='cyan', linewidth=2)
    ax.set_facecolor("black")
    ax.tick_params(colors='white', labelsize=6)
    fig.patch.set_facecolor("black")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(False)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def generate_html(score, bar_pct, chart_img):
    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta http-equiv='refresh' content='30'>
<title>Weather Intensity Score</title>
<style>
    body {{
        margin: 0;
        padding: 0;
        background-color: #111;
        font-family: Arial, sans-serif;
        color: white;
    }}
    .container {{
        display: flex;
        align-items: center;
        background-color: #7a5cff;
        padding: 5px 10px;
    }}
    .title {{
        font-weight: bold;
        font-size: 18px;
        margin-right: 15px;
    }}
    .score-box {{
        background-color: #222;
        color: #ff5555;
        font-size: 22px;
        font-weight: bold;
        padding: 4px 12px;
        margin-right: 15px;
    }}
    .chart {{
        height: 50px;
        margin-right: 15px;
    }}
    .bar-wrapper {{
        flex-grow: 1;
        background-color: #111;
        height: 12px;
        border-radius: 6px;
        overflow: hidden;
        margin-left: 10px;
        margin-right: 10px;
        border: 1px solid #333;
    }}
    .bar-fill {{
        height: 100%;
        background: linear-gradient(to right, #00ffff, #00aaff);
        width: {bar_pct}%;
    }}
    .bar-labels {{
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        padding-top: 2px;
        color: #fff;
    }}
</style>
</head>
<body>
    <div class="container">
        <div class="title">WEATHER INTENSITY SCORE</div>
        <div class="score-box">{score:.2f}</div>
        <img src="data:image/png;base64,{chart_img}" class="chart" alt="Score Chart" height="50">
        <div style="display: flex; flex-direction: column;">
            <div class="bar-wrapper">
                <div class="bar-fill"></div>
            </div>
            <div class="bar-labels">
                <span>QUIET</span><span>ACTIVE</span><span>EXTREME</span>
            </div>
        </div>
    </div>
</body>
</html>"""

def main():
    print("✅ Live weather score + chart HTML updater running...")
    while True:
        try:
            if json_path.exists():
                with open(json_path, "r") as f:
                    data = json.load(f)
                score = float(data.get("total_score", 0))
                ts = datetime.now()

                df = load_history()
                df = pd.concat([df, pd.DataFrame([{"timestamp": ts, "score": score}])])
                df = df.drop_duplicates(subset="timestamp")
                df = df.tail(60)
                save_history(df)

                bar_pct = min(max((score / 100) * 100, 0), 100)
                chart_img = plot_chart(df)
                html = generate_html(score, bar_pct, chart_img)

                with open(html_output, "w", encoding="utf-8") as f:
                    f.write(html)
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(30)

if __name__ == "__main__":
    main()
