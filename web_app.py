from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "dataset", "india")
USERS_PATH = os.path.join(BASE_DIR, "users.json")
BUYLIST_PATH = os.path.join(BASE_DIR, "buylist.json")

# ---------------- LOAD STOCK FILES ----------------
stocks_list = {}
if os.path.exists(DATASET_PATH):
    for file in os.listdir(DATASET_PATH):
        if file.endswith(".csv"):
            stocks_list[file.replace(".csv", "").upper()] = file


# ---------------- UTIL ----------------
# ---------------- UTIL ----------------
def load_csv(filename):
    return pd.read_csv(os.path.join(DATASET_PATH, filename))

def ensure_users():
    if not os.path.exists(USERS_PATH):
        with open(USERS_PATH, "w") as f:
            json.dump({}, f)

def ensure_buylist():
    if not os.path.exists(BUYLIST_PATH):
        with open(BUYLIST_PATH, "w") as f:
            json.dump({}, f)


# ---------------- AUTH ROUTES ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_users()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open(USERS_PATH) as f:
            users = json.load(f)

        if username in users and check_password_hash(users[username], password):
            session["user"] = username
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid Credentials")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    ensure_users()

    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        with open(USERS_PATH) as f:
            users = json.load(f)

        if username in users:
            return render_template("signup.html", error="User already exists")

        users[username] = password

        with open(USERS_PATH, "w") as f:
            json.dump(users, f, indent=4)

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ---------------- LOGIN PROTECTION ----------------
def login_required():
    if "user" not in session:
        return False
    return True


# ---------------- BROKER REDIRECT ----------------
@app.route("/go/<broker>/<stock>")
def go_to_broker(broker, stock):

    if not login_required():
        return redirect(url_for("login"))

    stock_lower = stock.lower()

    if broker == "groww":
        return redirect(f"https://groww.in/stocks/{stock_lower}")

    elif broker == "zerodha":
        return redirect(f"https://kite.zerodha.com/chart/web/tvc/NSE/{stock.upper()}")

    elif broker == "upstox":
        return redirect(f"https://upstox.com/stocks/{stock_lower}")

    return redirect(url_for("dashboard"))


# ---------------- METRICS ENGINE ----------------
def calculate_metrics(df):

    df["returns"] = df["Close"].pct_change()

    avg_return = df["returns"].mean() * 100
    volatility = df["returns"].std() * (252 ** 0.5) * 100

    sharpe = 0
    if df["returns"].std() != 0:
        sharpe = (df["returns"].mean() / df["returns"].std()) * (252 ** 0.5)

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()

    trend = "Uptrend" if df["MA20"].iloc[-1] > df["MA50"].iloc[-1] else "Downtrend"

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi = rsi_series.iloc[-1] if not rsi_series.empty else 0

    if volatility < 15:
        risk_level = "Low Risk"
    elif volatility < 30:
        risk_level = "Moderate Risk"
    else:
        risk_level = "High Risk"

    score = 0

    if sharpe > 1:
        score += 3
    elif sharpe > 0.5:
        score += 1
    else:
        score -= 1

    if 40 <= rsi <= 60:
        score += 2
    elif rsi > 75:
        score -= 2

    if trend == "Uptrend":
        score += 2
    else:
        score -= 1

    if score >= 5:
        recommendation = "Strong Buy"
    elif score >= 3:
        recommendation = "Buy"
    elif score >= 1:
        recommendation = "Hold"
    elif score >= -1:
        recommendation = "Sell"
    else:
        recommendation = "Strong Sell"

    confidence = min(100, abs(score) * 15)

    crash_alert = ""
    if df["returns"].min() < -0.08:
        crash_alert = "Market shows high downside movement!"

    return {
        "avg_return": round(avg_return, 2),
        "volatility": round(volatility, 2),
        "sharpe": round(sharpe, 2),
        "trend": trend,
        "rsi": round(rsi, 2),
        "score": score,
        "recommendation": recommendation,
        "confidence": confidence,
        "risk_level": risk_level,
        "crash_alert": crash_alert,
        "ma20": df["MA20"].fillna(0).tolist(),
        "ma50": df["MA50"].fillna(0).tolist()
    }


# ---------------- MAIN ROUTES ----------------
@app.route("/")
def home():
    if not login_required():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/buy")
def buy():

    if "user" not in session:
        return redirect(url_for("login"))

    ensure_buylist()

    with open(BUYLIST_PATH) as f:
        data = json.load(f)

    user = session["user"]
    user_buylist = data.get(user, [])

    return render_template("buy.html", buylist=user_buylist)

@app.route("/analyze", methods=["GET", "POST"])
def analyze():

    if not login_required():
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "analyze.html",
            stocks=list(stocks_list.keys()),
            result=None,
            selected_range="1Y",
            dates=[],
            prices=[],
            ma20=[],
            ma50=[],
            monthly_labels=[],
            monthly_values=[]
        )

    stock = request.form.get("stock")

    if stock not in stocks_list:
        return redirect(url_for("analyze"))

    df = load_csv(stocks_list[stock])

    df.columns = df.columns.str.strip()
    df.rename(columns={df.columns[0]: "Date"}, inplace=True)

    close_col = next((c for c in df.columns if c.lower() == "close"), None)

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")

    df.rename(columns={close_col: "Close"}, inplace=True)
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date")

    # Seasonal
    df["returns"] = df["Close"].pct_change()
    df["Month"] = df["Date"].dt.month
    monthly = df.groupby("Month")["returns"].mean() * 100
    monthly = monthly.round(2)

    metrics = calculate_metrics(df.copy())

    result = {
        "stock": stock,
        **metrics
    }

    return render_template(
        "analyze.html",
        stocks=list(stocks_list.keys()),
        result=result,
        selected_range="1Y",
        dates=df["Date"].dt.strftime("%Y-%m-%d").tolist(),
        prices=df["Close"].tolist(),
        ma20=metrics["ma20"],
        ma50=metrics["ma50"],
        monthly_labels=monthly.index.tolist(),
        monthly_values=monthly.tolist()
    )

@app.route("/add_to_buy", methods=["POST"])
def add_to_buy():

    if "user" not in session:
        return "Login Required", 401

    ensure_buylist()

    stock = request.form.get("stock")
    user = session["user"]

    with open(BUYLIST_PATH) as f:
        data = json.load(f)

    if user not in data:
        data[user] = []

    if stock not in data[user]:
        data[user].append(stock)

    with open(BUYLIST_PATH, "w") as f:
        json.dump(data, f, indent=4)

    return "Added"

@app.route("/watchlist")
def watchlist():

    if "user" not in session:
        return redirect(url_for("login"))

    WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.json")

    if not os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, "w") as f:
            json.dump({}, f)

    with open(WATCHLIST_PATH) as f:
        data = json.load(f)

    user = session["user"]
    user_watchlist = data.get(user, [])

    return render_template("watchlist.html", watchlist=user_watchlist)

if __name__ == "__main__":
    app.run(debug=True)