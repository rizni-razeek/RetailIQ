import pandas as pd
import numpy as np

rng = np.random.default_rng(42)

dates = pd.date_range("2026-05-01", "2026-08-25", freq="D")

categories = {
    "BEVERAGES": 170000,
    "DAIRY": 85000,
    "GROCERY I": 240000,
}

rows = []

for family, base in categories.items():
    for date in dates:
        weekend = 1.18 if date.dayofweek >= 5 else 1.0
        seasonal = 1 + 0.08 * np.sin((date.dayofyear / 365) * 2 * np.pi)
        onpromotion = int(rng.integers(0, 5))
        promotion = 1 + (0.025 * onpromotion)
        noise = rng.normal(1.0, 0.07)

        sales = max(
            0,
            base * weekend * seasonal * promotion * noise
        )

        rows.append([
            date.date(),
            family,
            round(sales, 2),
            onpromotion
        ])

df = pd.DataFrame(
    rows,
    columns=["date", "family", "sales", "onpromotion"]
)

df.to_csv("docs/retailiq_demo_2026.csv", index=False)

print("Demo CSV created successfully")
print("Rows:", len(df))
print("Date range:", df["date"].min(), "to", df["date"].max())
print(df.groupby("family").size())