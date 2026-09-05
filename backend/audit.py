from datetime import datetime, timezone
from typing import Any


AUDIT_LOG: list[dict[str, Any]] = []


def record_audit(
    transaction_id: str,
    risk_probability: float,
    regional_risk: float,
    recommended_action: str,
    final_action: str,
    reasons: list[str],
    reviewer: str | None = None,
) -> dict[str, Any]:

    record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "transaction_id": transaction_id,

        "risk_probability": round(
            float(risk_probability),
            6
        ),

        "risk_score": round(
            float(risk_probability) * 100,
            2
        ),

        "regional_risk": round(
            float(regional_risk),
            2
        ),

        "recommended_action": recommended_action,

        "final_action": final_action,

        "reasons": reasons,

        "reviewer": reviewer,
    }

    AUDIT_LOG.append(record)

    return record