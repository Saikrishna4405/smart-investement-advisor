from flask import Flask, render_template, request
from data_loader import load_data
from analysis import calculate_metrics
from advisor import investment_decision
from predictor import predict_next_price
from datetime import timedelta
import pandas as pd
import os

app = Flask(__name__)

# ---------------- STOCK LIST ----------------
stocks_list = {}

dataset_path = os.path.join("dataset", "india")

if os.path.exists(dataset_path):
    for file in os.listdir(dataset_path):
        if file.endswith(".csv"):
            stock_name = file.replace(".NS.csv", "")
            stocks_list[stock_name] = file
else:
    print("Dataset folder not found")

# ---------------- HOME ROUTE ----------------
@app.route("/")
def home():
    return render_template(
        "home.html",
        stocks=stocks_list.keys(),
        result=None,
        chart_data=None,
        selected_range="1Y"
    )

# ---------------- ANALYZE ROUTE ----------------
@app.route("/analyze", methods=["POST"])
def analyze():

    selected_stock = request.form.get("stock")
    selected_range = request.form.get("range", "1Y")

    if selected_stock not in stocks_list:
        return "Invalid stock selected"

    filename = stocks_list[selected_stock]
    data = load_data(filename)

    data["Date"] = pd.to_datetime(data["Date"])
    data = data.sort_values("Date")

    full_data = data.copy()

    # Calculate MA on full data
    full_data['MA20'] = full_data['Close'].rolling(20).mean()
    full_data['MA50'] = full_data['Close'].rolling(50).mean()

    latest_date = full_data["Date"].max()

    if selected_range == "1M":
        start_date = latest_date - timedelta(days=30)
        data_chart = full_data[full_data["Date"] >= start_date]
    elif selected_range == "3M":
        start_date = latest_date - timedelta(days=90)
        data_chart = full_data[full_data["Date"] >= start_date]
    elif selected_range == "6M":
        start_date = latest_date - timedelta(days=180)
        data_chart = full_data[full_data["Date"] >= start_date]
    elif selected_range == "1Y":
        start_date = latest_date - timedelta(days=365)
        data_chart = full_data[full_data["Date"] >= start_date]
    elif selected_range == "5Y":
        start_date = latest_date - timedelta(days=1825)
        data_chart = full_data[full_data["Date"] >= start_date]
    else:
        data_chart = full_data

    # ---- METRICS ----
    metrics = calculate_metrics(full_data)

    recommendation, score = investment_decision(
        metrics["volatility"],
        metrics["avg_return"],
        metrics["trend"]
    )

    # ---- ML PREDICTION ----
    ml_result = predict_next_price(full_data)

    result = {
        "stock": selected_stock,
        "volatility": metrics["volatility"],
        "avg_return": metrics["avg_return"],
        "trend": metrics["trend"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "cagr": metrics["cagr"],
        "risk_level": metrics["risk_level"],
        "rsi": metrics["rsi"],
        "prediction": ml_result["prediction"],
        "mae": ml_result["mae"],
        "r2": ml_result["r2"],
        "recommendation": recommendation,
        "score": score
    }

    # ---- CHART DATA ----
    chart_data = {
        "dates": data_chart["Date"].dt.strftime("%Y-%m-%d").tolist(),
        "close": data_chart["Close"].tolist(),
        "ma20": data_chart["MA20"].fillna(0).tolist(),
        "ma50": data_chart["MA50"].fillna(0).tolist()
    }

    # ---- PREDICTION CHART ----
    prediction_chart = {
        "actual": ml_result["actual_test"],
        "predicted": ml_result["predicted_test"]
    }

    return render_template(
        "home.html",
        stocks=stocks_list.keys(),
        result=result,
        chart_data=chart_data,
        prediction_chart=prediction_chart,
        selected_range=selected_range
    )

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    import pandas as pd

    app.run(debug=True)
