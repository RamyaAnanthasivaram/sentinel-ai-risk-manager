from pathlib import Path
import sqlite3
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "sentinel.db"


class SpikeStore:

    def __init__(self) -> None:

        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self._initialize()

        self._seed_pipeline_results()


    # ======================================================
    # DATABASE
    # ======================================================

    def _connect(self) -> sqlite3.Connection:

        connection = sqlite3.connect(
            DB_PATH,
            check_same_thread=False
        )

        connection.row_factory = sqlite3.Row

        return connection


    # ======================================================
    # TABLE
    # ======================================================

    def _initialize(self) -> None:

        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS fraud_spikes (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    time_bin INTEGER NOT NULL UNIQUE,

                    spike_scope TEXT NOT NULL,

                    transactions INTEGER NOT NULL,

                    high_risk_rate REAL NOT NULL,

                    rate_increase REAL NOT NULL,

                    z_score REAL NOT NULL,

                    severity TEXT NOT NULL,

                    source TEXT NOT NULL,

                    created_at TEXT NOT NULL
                )
            """)


    # ======================================================
    # HISTORICAL PIPELINE RESULTS
    # ======================================================

    def _seed_pipeline_results(self) -> None:

        spikes = [

            (
                143,
                "GLOBAL",
                7449,
                0.24,
                0.200781,
                5.171563,
                "HIGH",
                "HISTORICAL_PIPELINE",
                "2026-09-04T00:00:00+00:00"
            ),

            (
                1384,
                "GLOBAL",
                8695,
                0.15,
                0.110781,
                3.609290,
                "MEDIUM",
                "HISTORICAL_PIPELINE",
                "2026-09-04T00:00:00+00:00"
            )

        ]


        with self._connect() as connection:

            for spike in spikes:

                connection.execute("""
                    INSERT OR IGNORE INTO fraud_spikes (

                        time_bin,
                        spike_scope,
                        transactions,
                        high_risk_rate,
                        rate_increase,
                        z_score,
                        severity,
                        source,
                        created_at

                    )

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, spike)


    # ======================================================
    # LIST
    # ======================================================

    def list_spikes(
        self
    ) -> list[dict[str, Any]]:

        with self._connect() as connection:

            rows = connection.execute("""
                SELECT *
                FROM fraud_spikes
                ORDER BY z_score DESC
            """).fetchall()


        return [
            dict(row)
            for row in rows
        ]


    # ======================================================
    # SUMMARY
    # ======================================================

    def summary(
        self
    ) -> dict[str, Any]:

        with self._connect() as connection:

            total = connection.execute("""
                SELECT COUNT(*)
                FROM fraud_spikes
            """).fetchone()[0]


            high = connection.execute("""
                SELECT COUNT(*)
                FROM fraud_spikes
                WHERE severity = 'HIGH'
            """).fetchone()[0]


            medium = connection.execute("""
                SELECT COUNT(*)
                FROM fraud_spikes
                WHERE severity = 'MEDIUM'
            """).fetchone()[0]


            maximum = connection.execute("""
                SELECT MAX(z_score)
                FROM fraud_spikes
            """).fetchone()[0]


        return {
            "confirmed_spikes": int(total),
            "high_severity": int(high),
            "medium_severity": int(medium),
            "max_z_score": float(maximum or 0)
        }


spike_store = SpikeStore()