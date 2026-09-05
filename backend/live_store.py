from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "sentinel.db"


class LiveStore:

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            DB_PATH,
            check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:

        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL UNIQUE,
                    event_time TEXT NOT NULL,
                    amount REAL NOT NULL,

                    risk_probability REAL NOT NULL,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,

                    regional_risk REAL NOT NULL DEFAULT 0,
                    decision TEXT NOT NULL,

                    region_key TEXT,
                    customer_id TEXT,
                    merchant_id TEXT,
                    device_id TEXT,
                    payment_method TEXT,

                    reasons TEXT,
                    source TEXT
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    case_id TEXT NOT NULL UNIQUE,
                    transaction_id TEXT NOT NULL,

                    risk_score REAL NOT NULL,
                    regional_risk REAL NOT NULL,

                    reasons TEXT,

                    status TEXT NOT NULL DEFAULT 'PENDING',

                    reviewer TEXT,
                    resolution TEXT,
                    notes TEXT,

                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    timestamp TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,

                    risk_probability REAL NOT NULL,
                    risk_score REAL NOT NULL,
                    regional_risk REAL NOT NULL,

                    recommended_action TEXT NOT NULL,
                    final_action TEXT NOT NULL,

                    reasons TEXT,
                    reviewer TEXT
                )
            """)

    # ------------------------------------------------------
    # Transaction storage
    # ------------------------------------------------------

    def save_transaction(
        self,
        transaction: dict[str, Any]
    ) -> dict[str, Any]:

        import json

        try:
            with self._connect() as connection:

                connection.execute("""
                    INSERT INTO transactions (
                        transaction_id,
                        event_time,
                        amount,
                        risk_probability,
                        risk_score,
                        risk_level,
                        regional_risk,
                        decision,
                        region_key,
                        customer_id,
                        merchant_id,
                        device_id,
                        payment_method,
                        reasons,
                        source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaction["transaction_id"],
                    transaction["event_time"],
                    transaction["amount"],
                    transaction["risk_probability"],
                    transaction["risk_score"],
                    transaction["risk_level"],
                    transaction["regional_risk"],
                    transaction["decision"],
                    transaction.get("region_key"),
                    transaction.get("customer_id"),
                    transaction.get("merchant_id"),
                    transaction.get("device_id"),
                    transaction.get("payment_method"),
                    json.dumps(
                        transaction.get("reasons", [])
                    ),
                    transaction.get("source", "api")
                ))

        except sqlite3.IntegrityError:
            # Idempotent behavior for repeated transaction ID
            pass

        return self.get_transaction(
            transaction["transaction_id"]
        )

    def get_transaction(
        self,
        transaction_id: str
    ) -> dict[str, Any] | None:

        with self._connect() as connection:

            row = connection.execute("""
                SELECT *
                FROM transactions
                WHERE transaction_id = ?
            """, (transaction_id,)).fetchone()

        if row is None:
            return None

        result = dict(row)

        import json

        try:
            result["reasons"] = json.loads(
                result["reasons"] or "[]"
            )
        except json.JSONDecodeError:
            result["reasons"] = []

        return result

    def recent_transactions(
        self,
        limit: int = 50
    ) -> list[dict[str, Any]]:

        with self._connect() as connection:

            rows = connection.execute("""
                SELECT *
                FROM transactions
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        import json

        results = []

        for row in rows:

            item = dict(row)

            try:
                item["reasons"] = json.loads(
                    item["reasons"] or "[]"
                )
            except json.JSONDecodeError:
                item["reasons"] = []

            results.append(item)

        return results

    # ------------------------------------------------------
    # Regional history
    # ------------------------------------------------------

    def regional_baseline(
        self,
        region_key: str
    ) -> dict[str, float]:

        with self._connect() as connection:

            row = connection.execute("""
                SELECT
                    COUNT(*) AS transaction_count,
                    AVG(risk_score) AS avg_risk,
                    AVG(
                        CASE
                            WHEN risk_score >= 76
                            THEN 1.0
                            ELSE 0.0
                        END
                    ) AS high_risk_rate
                FROM transactions
                WHERE region_key = ?
            """, (region_key,)).fetchone()

        return {
            "transaction_count": int(
                row["transaction_count"] or 0
            ),
            "avg_risk": float(
                row["avg_risk"] or 0
            ),
            "high_risk_rate": float(
                row["high_risk_rate"] or 0
            ),
        }

    # ------------------------------------------------------
    # Review queue
    # ------------------------------------------------------

    def create_review_case(
        self,
        case: dict[str, Any]
    ) -> dict[str, Any]:

        import json

        with self._connect() as connection:

            connection.execute("""
                INSERT INTO review_cases (
                    case_id,
                    transaction_id,
                    risk_score,
                    regional_risk,
                    reasons,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """, (
                case["case_id"],
                case["transaction_id"],
                case["risk_score"],
                case["regional_risk"],
                json.dumps(
                    case.get("reasons", [])
                ),
                case["created_at"]
            ))

        return self.get_review_case(
            case["case_id"]
        )

    def get_review_case(
        self,
        case_id: str
    ) -> dict[str, Any] | None:

        with self._connect() as connection:

            row = connection.execute("""
                SELECT *
                FROM review_cases
                WHERE case_id = ?
            """, (case_id,)).fetchone()

        if row is None:
            return None

        result = dict(row)

        import json

        try:
            result["reasons"] = json.loads(
                result["reasons"] or "[]"
            )
        except json.JSONDecodeError:
            result["reasons"] = []

        return result

    def review_cases(
        self,
        status: str | None = None
    ) -> list[dict[str, Any]]:

        with self._connect() as connection:

            if status:

                rows = connection.execute("""
                    SELECT *
                    FROM review_cases
                    WHERE status = ?
                    ORDER BY id DESC
                """, (status,)).fetchall()

            else:

                rows = connection.execute("""
                    SELECT *
                    FROM review_cases
                    ORDER BY id DESC
                """).fetchall()

        import json

        results = []

        for row in rows:

            item = dict(row)

            try:
                item["reasons"] = json.loads(
                    item["reasons"] or "[]"
                )
            except json.JSONDecodeError:
                item["reasons"] = []

            results.append(item)

        return results

    def resolve_review(
        self,
        case_id: str,
        resolution: str,
        reviewer: str,
        notes: str = ""
    ) -> dict[str, Any] | None:

        now = datetime.now(
            timezone.utc
        ).isoformat()

        with self._connect() as connection:

            connection.execute("""
                UPDATE review_cases

                SET
                    status = 'RESOLVED',
                    reviewer = ?,
                    resolution = ?,
                    notes = ?,
                    resolved_at = ?

                WHERE case_id = ?
            """, (
                reviewer,
                resolution,
                notes,
                now,
                case_id
            ))

        return self.get_review_case(
            case_id
        )

    # ------------------------------------------------------
    # Audit
    # ------------------------------------------------------

    def save_audit(
        self,
        record: dict[str, Any]
    ) -> None:

        import json

        with self._connect() as connection:

            connection.execute("""
                INSERT INTO audit_log (
                    timestamp,
                    transaction_id,
                    risk_probability,
                    risk_score,
                    regional_risk,
                    recommended_action,
                    final_action,
                    reasons,
                    reviewer
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["timestamp"],
                record["transaction_id"],
                record["risk_probability"],
                record["risk_score"],
                record["regional_risk"],
                record["recommended_action"],
                record["final_action"],
                json.dumps(
                    record.get("reasons", [])
                ),
                record.get("reviewer")
            ))

    # ------------------------------------------------------
    # Dashboard statistics
    # ------------------------------------------------------

    def stats(self) -> dict[str, Any]:

        with self._connect() as connection:

            total = connection.execute("""
                SELECT COUNT(*) FROM transactions
            """).fetchone()[0]

            high_risk = connection.execute("""
                SELECT COUNT(*)
                FROM transactions
                WHERE risk_score >= 76
            """).fetchone()[0]

            review_count = connection.execute("""
                SELECT COUNT(*)
                FROM review_cases
                WHERE status = 'PENDING'
            """).fetchone()[0]

            blocked = connection.execute("""
                SELECT COUNT(*)
                FROM transactions
                WHERE decision = 'BLOCK'
            """).fetchone()[0]

            exposure = connection.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE risk_score >= 76
            """).fetchone()[0]

        return {
            "total_transactions": total,
            "high_risk_transactions": high_risk,
            "pending_reviews": review_count,
            "blocked_transactions": blocked,
            "high_risk_exposure": round(
                float(exposure),
                2
            )
        }

        # ------------------------------------------------------
    # Audit records
    # ------------------------------------------------------

    def audit_records(
        self,
        limit: int = 100
    ) -> list[dict]:

        import json

        with self._connect() as connection:

            rows = connection.execute("""
                SELECT *
                FROM audit_log
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        results = []

        for row in rows:

            item = dict(row)

            try:
                item["reasons"] = json.loads(
                    item["reasons"] or "[]"
                )

            except json.JSONDecodeError:

                item["reasons"] = []

            results.append(item)

        return results
        # ------------------------------------------------------
    # Policy configuration
    # ------------------------------------------------------

    def get_policy(self) -> dict:
        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            connection.execute("""
                INSERT OR IGNORE INTO settings
                (key, value)
                VALUES ('allow_threshold', '0.58')
            """)

            connection.execute("""
                INSERT OR IGNORE INTO settings
                (key, value)
                VALUES ('block_threshold', '0.76')
            """)

            rows = connection.execute("""
                SELECT key, value
                FROM settings
                WHERE key IN (
                    'allow_threshold',
                    'block_threshold'
                )
            """).fetchall()

        values = {
            row["key"]: float(row["value"])
            for row in rows
        }

        return {
            "allow_threshold": values["allow_threshold"],
            "block_threshold": values["block_threshold"]
        }


    def update_policy(
        self,
        allow_threshold: float,
        block_threshold: float
    ) -> dict:

        if not 0 < allow_threshold < 1:
            raise ValueError(
                "Allow threshold must be between 0 and 1."
            )

        if not 0 < block_threshold < 1:
            raise ValueError(
                "Block threshold must be between 0 and 1."
            )

        if allow_threshold >= block_threshold:
            raise ValueError(
                "Allow threshold must be lower than block threshold."
            )

        with self._connect() as connection:

            connection.execute("""
                INSERT OR REPLACE INTO settings
                (key, value)
                VALUES ('allow_threshold', ?)
            """, (str(allow_threshold),))

            connection.execute("""
                INSERT OR REPLACE INTO settings
                (key, value)
                VALUES ('block_threshold', ?)
            """, (str(block_threshold),))

        return self.get_policy()


live_store = LiveStore()