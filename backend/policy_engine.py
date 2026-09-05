from typing import Any


def evaluate_policy(
    risk_probability: float,
    regional_risk: float = 0.0,
    incident_severity: str = "NONE",
    human_review_required: bool = False,
    allow_threshold: float = 0.58,
    block_threshold: float = 0.76,
) -> dict[str, Any]:

    risk_probability = float(risk_probability)
    regional_risk = float(regional_risk)

    reasons: list[str] = []

    # Human review takes priority.
    if human_review_required:

        action = "REVIEW"
        reasons.append("human review policy")

    elif (
        incident_severity == "CRITICAL"
        and risk_probability >= allow_threshold
    ):

        action = "BLOCK"
        reasons.append("critical active incident")

    elif risk_probability >= block_threshold:

        action = "BLOCK"
        reasons.append("high transaction risk")

    elif risk_probability >= allow_threshold:

        action = "REVIEW"
        reasons.append("elevated transaction risk")

    else:

        action = "ALLOW"

    if regional_risk >= 60:
        reasons.append("regional anomaly")

    if incident_severity in {
        "HIGH",
        "CRITICAL"
    }:
        reasons.append(
            f"{incident_severity.lower()} active incident"
        )

    return {
        "action": action,
        "risk_probability": round(
            risk_probability,
            6
        ),
        "risk_score": round(
            risk_probability * 100,
            2
        ),
        "regional_risk": round(
            regional_risk,
            2
        ),
        "incident_severity": incident_severity,
        "reasons": reasons
    }