from pathlib import Path
import json
from typing import Any

import pandas as pd
from catboost import CatBoostClassifier


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    BASE_DIR
    / "model"
    / "sentinel_v1_full.cbm"
)

CONFIG_PATH = (
    BASE_DIR
    / "model"
    / "sentinel_v1_config.json"
)


class RiskEngine:

    def __init__(self) -> None:

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found: {MODEL_PATH}"
            )

        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Config not found: {CONFIG_PATH}"
            )

        self.model = CatBoostClassifier()

        self.model.load_model(
            str(MODEL_PATH)
        )

        with CONFIG_PATH.open(
            "r",
            encoding="utf-8"
        ) as file:

            self.config = json.load(file)

        self.features = self.config["features"]

        self.categorical_features = set(
            self.config.get(
                "categorical_features",
                []
            )
        )

        print(
            f"✅ Sentinel model loaded "
            f"({len(self.features)} features)"
        )


    def prepare_features(
        self,
        supplied_features: dict[str, Any]
    ) -> pd.DataFrame:
        """
        Build exactly the feature schema expected
        by the trained CatBoost model.
        """

        row: dict[str, Any] = {}

        for feature in self.features:

            if feature in supplied_features:

                value = supplied_features[
                    feature
                ]

            elif feature in self.categorical_features:

                value = "UNKNOWN"

            else:

                value = None

            row[feature] = value

        frame = pd.DataFrame([row])

        for column in self.categorical_features:

            frame[column] = (
                frame[column]
                .fillna("UNKNOWN")
                .astype(str)
            )

        return frame


    def score(
        self,
        supplied_features: dict[str, Any]
    ) -> dict[str, Any]:

        frame = self.prepare_features(
            supplied_features
        )

        probability = float(
            self.model.predict_proba(
                frame
            )[0][1]
        )

        risk_score = probability * 100

        # Sentinel risk bands
        if risk_score < 30:

            risk_level = "LOW"

        elif risk_score < 58:

            risk_level = "MEDIUM"

        elif risk_score < 76:

            risk_level = "HIGH"

        else:

            risk_level = "CRITICAL"

        return {
            "risk_probability": round(
                probability,
                6
            ),

            "risk_score": round(
                risk_score,
                2
            ),

            "risk_level": risk_level,

            "model_version": "Sentinel-V1"
        }


risk_engine = RiskEngine()