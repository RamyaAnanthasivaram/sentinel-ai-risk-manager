import pandas as pd
from catboost import CatBoostClassifier


MODEL_PATH = "model/sentinel_v1_full.cbm"
DATA_PATH = "data/sentinel_inference.parquet"


# Load model
model = CatBoostClassifier()
model.load_model(MODEL_PATH)

# Load real feature store
df = pd.read_parquet(DATA_PATH)

# Exact feature schema from trained model
features = model.feature_names_

# Prepare feature matrix
X = df[features].copy()

# Convert CatBoost categorical fields
cat_indices = model.get_cat_feature_indices()

for i in cat_indices:
    column = features[i]

    X[column] = (
        X[column]
        .fillna("UNKNOWN")
        .astype(str)
    )

# Score the real transactions
df["risk_probability"] = (
    model.predict_proba(X)[:, 1]
)

df["risk_score"] = (
    df["risk_probability"] * 100
)

# Show highest-risk transactions
result = (
    df[
        [
            "TransactionID",
            "TransactionAmt",
            "risk_probability",
            "risk_score"
        ]
    ]
    .sort_values(
        "risk_score",
        ascending=False
    )
    .head(20)
)

print("\n==============================")
print("TOP SENTINEL RISK TRANSACTIONS")
print("==============================\n")

print(
    result.to_string(index=False)
)