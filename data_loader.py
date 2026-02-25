import pandas as pd
import os

def load_data(filename):
    path = os.path.join("dataset", "india", filename)

    if not os.path.exists(path):
        raise Exception(f"File not found: {path}")

    data = pd.read_csv(path)

    # Flatten multi-level columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Clean column names
    data.columns = [col.strip().lower() for col in data.columns]

    # Detect close column
    close_col = next((col for col in data.columns if "close" in col), None)

    if close_col is None:
        raise Exception(f"No Close column found. Columns: {data.columns}")

    # Detect date column
    date_col = next((col for col in data.columns if "date" in col), None)

    if date_col:
        data = data[[date_col, close_col]]
        data.columns = ["Date", "Close"]
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    else:
        data = data[[close_col]]
        data.columns = ["Close"]
        data["Date"] = pd.date_range(start="2000-01-01", periods=len(data), freq="D")
        data = data[["Date", "Close"]]

    data["Close"] = pd.to_numeric(data["Close"], errors="coerce")
    data = data.dropna()

    if data.empty:
        raise Exception("Dataset is empty after cleaning")

    return data
