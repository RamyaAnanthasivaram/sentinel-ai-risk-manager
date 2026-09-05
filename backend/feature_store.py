from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = (
    BASE_DIR
    / "data"
    / "sentinel_inference.parquet"
)


class FeatureStore:

    def __init__(self) -> None:

        if not DATA_PATH.exists():
            raise FileNotFoundError(
                f"Inference dataset not found: {DATA_PATH}"
            )

        self.data = pd.read_parquet(
            DATA_PATH
        )

        self.data["TransactionID"] = (
            self.data["TransactionID"]
            .astype(str)
        )

        self.index = (
            self.data
            .set_index("TransactionID")
        )

        print(
            f"✅ Feature store loaded "
            f"({len(self.data)} transactions)"
        )

    def get(
        self,
        transaction_id: str
    ) -> dict:

        transaction_id = str(
            transaction_id
        )

        if transaction_id not in self.index.index:
            raise KeyError(
                f"Transaction not found: "
                f"{transaction_id}"
            )

        row = self.index.loc[
            transaction_id
        ]

        return row.to_dict()


feature_store = FeatureStore()