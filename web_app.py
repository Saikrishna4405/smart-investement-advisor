from flask import Flask, render_template, request, redirect, session
from data_loader import load_data
from analysis import calculate_metrics
from advisor import investment_decision
from predictor import predict_next_price
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import json
import os

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ---------------- PATH SETUP ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_DIR, "users.json")
WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.json")
DATASET_PATH = os.path.join(BASE_DIR, "dataset", "india")

# ---------------- STOCK LIST ----------------
stocks_list = {}

if os.path.exists(DATASET_PATH):
    for file in os.listdir(DATASET_PATH):
        if file.endswith(".csv"):
            stock_name = file.replace(".NS.csv", "")
            stocks_list[stock_name] = file

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template(
        "home.html",
        stocks=stocks_list.keys(),
        result=None,
        chart_data=None,
        selected_range="1Y"
    )

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not os.path.exists(USERS_PATH):
            with open(USERS_PATH, "w") as f:
                json.dump({}, f)

        with open(USERS_PATH, "r") as f:
            users = json.load(f)

        if username in users:
            return "User already exists"

        users[username] = generate_password_hash(password)

        with open(USERS_PATH, "w") as f:
            json.dump(users, f)

        return redirect("/login")

    return render_template("signup.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not os.path.exists(USERS_PATH):
            return "No users found"

        with open(USERS_PATH, "r") as f:
            users = json.load(f)

        if username in users and check_password_hash(users[username], password):
            session["username"] = username
            return redirect("/dashboard")
        else:
            return "Invalid credentials"

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")

    username = session["username"]

    if not os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, "w") as f:
            json.dump({}, f)

    with open(WATCHLIST_PATH, "r") as f:
        data = json.load(f)

    user_watchlist = data.get(username, [])

    return render_template("dashboard.html", watchlist=user_watchlist)


# ---------------- ADD WATCHLIST ----------------
@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    if "username" not in session:
        return redirect("/login")

    stock = request.form.get("stock")
    username = session["username"]

    if not os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, "w") as f:
            json.dump({}, f)

    with open(WATCHLIST_PATH, "r") as f:
        data = json.load(f)

    if username not in data:
        data[username] = []

    if stock and stock not in data[username]:
        data[username].append(stock)

    with open(WATCHLIST_PATH, "w") as f:
        json.dump(data, f)

    return redirect("/dashboard")


# ---------------- ANALYZE ----------------
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

    metrics = calculate_metrics(full_data)

    recommendation, score = investment_decision(
        metrics["volatility"],
        metrics["avg_return"],
        metrics["trend"]
    )

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

    chart_data = {
        "dates": data_chart["Date"].dt.strftime("%Y-%m-%d").tolist(),
        "close": data_chart["Close"].tolist(),
        "ma20": data_chart["MA20"].fillna(0).tolist(),
        "ma50": data_chart["MA50"].fillna(0).tolist()
    }

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

@app.route("/remove_watchlist", methods=["POST"])
def remove_watchlist():
    if "username" not in session:
        return redirect("/login")

    stock = request.form.get("stock")
    username = session["username"]

    with open(WATCHLIST_PATH, "r") as f:
        data = json.load(f)

    if username in data and stock in data[username]:
        data[username].remove(stock)

    with open(WATCHLIST_PATH, "w") as f:
        json.dump(data, f)

    return redirect("/dashboard")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()