from typing import Any
from datetime import datetime, timezone
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .feature_store import feature_store
from .risk_engine import risk_engine
from .policy_engine import evaluate_policy
from .live_store import live_store
from .incident_engine import incident_engine
from .spike_engine import spike_engine

from collections import defaultdict
from statistics import mean, pstdev


# ==========================================================
# APP
# ==========================================================

app = FastAPI(
    title="Sentinel AI Risk Manager",
    description=(
        "AI-powered transaction risk scoring, "
        "policy decisioning and audit service."
    ),
    version="4.0.0",
)


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",

        # Production frontend
        "https://sentinel-frontend-hgp5.onrender.com",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# ==========================================================
# REQUEST MODELS
# ==========================================================

class PolicyUpdateRequest(BaseModel):

    allow_threshold: float = Field(
        gt=0,
        lt=1
    )

    block_threshold: float = Field(
        gt=0,
        lt=1
    )


class LiveTransactionRequest(BaseModel):

    transaction_id: str

    amount: float = Field(
        gt=0
    )

    customer_id: str | None = None

    merchant_id: str | None = None

    payment_method: str | None = None

    device_id: str | None = None

    ip_address: str | None = None

    region: str | None = None

    model_features: dict[str, Any] = {}


# ==========================================================
# HEALTH
# ==========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "sentinel",
        "version": "4.0.0",
    }


# ==========================================================
# MODEL INFO
# ==========================================================

@app.get("/api/model")
def model_info():

    return {
        "model_version": "Sentinel-V1",

        "feature_count":
            len(
                risk_engine.features
            ),

        "categorical_feature_count":
            len(
                risk_engine.categorical_features
            ),
    }


# ==========================================================
# MODEL FEATURE BUILDER
# ==========================================================

def build_model_features(
    transaction: LiveTransactionRequest
) -> tuple[dict[str, Any], str]:

    """
    Build model features for a transaction.

    Priority:

    1. Explicit model_features from request.
    2. Existing transaction from feature store.
    3. Simulator scenario template for a new
       transaction.

    Simulator scenarios:

        amount < 100
            -> low-risk / ALLOW template

        100 <= amount < 200
            -> review-risk / REVIEW template

        amount >= 200
            -> high-risk / BLOCK template
    """

    # ------------------------------------------------------
    # 1. Explicit model features
    # ------------------------------------------------------

    if transaction.model_features:

        return (
            dict(
                transaction.model_features
            ),
            "request"
        )


    # ------------------------------------------------------
    # 2. Existing feature-store transaction
    # ------------------------------------------------------

    try:

        stored = feature_store.get(
            transaction.transaction_id
        )

        stored = dict(
            stored
        )

        stored.pop(
            "isFraud",
            None
        )

        return (
            stored,
            "feature_store"
        )

    except KeyError:

        pass


    # ------------------------------------------------------
    # 3. Select simulator scenario
    # ------------------------------------------------------

    amount = float(
        transaction.amount
    )


    if amount < 100:

        template_id = "3488966"

        scenario = "simulator_allow"


    elif amount < 200:

        template_id = "3489226"

        scenario = "simulator_review"


    else:

        template_id = "3492819"

        scenario = "simulator_block"


    # ------------------------------------------------------
    # 4. Load template
    # ------------------------------------------------------

    try:

        stored = feature_store.get(
            template_id
        )

    except KeyError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Simulator template transaction "
                f"{template_id} was not found: {exc}"
            )
        )


    stored = dict(
        stored
    )


    stored.pop(
        "isFraud",
        None
    )


    return (
        stored,
        scenario
    )


# ==========================================================
# LIVE TRANSACTION INGESTION
# ==========================================================

@app.post("/api/transactions")
def ingest_transaction(
    transaction: LiveTransactionRequest
):

    # ------------------------------------------------------
    # 1. Build model features
    # ------------------------------------------------------

    features, source = (
        build_model_features(
            transaction
        )
    )


    # ------------------------------------------------------
    # 2. Preserve exact transaction amount
    # ------------------------------------------------------

    features[
        "TransactionAmt"
    ] = transaction.amount


    # ------------------------------------------------------
    # 3. Region
    # ------------------------------------------------------

    if transaction.region:

        features.setdefault(
            "region_key",
            transaction.region
        )


    # ------------------------------------------------------
    # 4. Sentinel model
    # ------------------------------------------------------

    try:

        risk = risk_engine.score(
            features
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Risk scoring failed: "
                f"{exc}"
            )
        )


    risk_probability = float(
        risk["risk_probability"]
    )


    risk_score = float(
        risk["risk_score"]
    )


    # ------------------------------------------------------
    # 5. Determine region
    # ------------------------------------------------------

    region_key = (
        features.get(
            "region_key"
        )
    )


    if not region_key:

        region_key = (
            transaction.region
            or
            "UNKNOWN"
        )


    region_key = str(
        region_key
    )


    # ------------------------------------------------------
    # 6. Dynamic regional context
    # ------------------------------------------------------

    regional_baseline = (
        live_store.regional_baseline(
            region_key
        )
    )


    regional_risk = 0.0

    regional_reason = None


    baseline_count = int(
        regional_baseline[
            "transaction_count"
        ]
    )


    baseline_avg_risk = float(
        regional_baseline[
            "avg_risk"
        ]
    )


    if baseline_count >= 20:

        risk_shift = (
            risk_score -
            baseline_avg_risk
        )


        regional_risk = max(
            0.0,
            min(
                100.0,
                risk_shift * 2
            )
        )


        if regional_risk >= 60:

            regional_reason = (
                "regional risk above historical baseline"
            )


    # ------------------------------------------------------
    # 7. Current policy
    # ------------------------------------------------------

    current_policy = (
        live_store.get_policy()
    )


    decision = evaluate_policy(
        risk_probability=
            risk_probability,

        regional_risk=
            regional_risk,

        allow_threshold=
            current_policy[
                "allow_threshold"
            ],

        block_threshold=
            current_policy[
                "block_threshold"
            ],
    )


    # ------------------------------------------------------
    # 8. Add regional reason
    # ------------------------------------------------------

    if regional_reason:

        if (
            regional_reason
            not in
            decision["reasons"]
        ):

            decision["reasons"].append(
                regional_reason
            )


    # ------------------------------------------------------
    # 9. Event time
    # ------------------------------------------------------

    event_time = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


    # ------------------------------------------------------
    # 10. Store transaction
    # ------------------------------------------------------

    stored_transaction = {

        "transaction_id":
            transaction.transaction_id,

        "event_time":
            event_time,

        "amount":
            transaction.amount,

        "risk_probability":
            risk_probability,

        "risk_score":
            risk_score,

        "risk_level":
            risk["risk_level"],

        "regional_risk":
            regional_risk,

        "decision":
            decision["action"],

        "region_key":
            region_key,

        "customer_id":
            transaction.customer_id,

        "merchant_id":
            transaction.merchant_id,

        "device_id":
            transaction.device_id,

        "payment_method":
            transaction.payment_method,

        "reasons":
            decision["reasons"],

        "source":
            (
                "simulator"
                if source.startswith(
                    "simulator_"
                )
                else source
            ),
    }


    saved = (
        live_store.save_transaction(
            stored_transaction
        )
    )


    if saved is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "Transaction could not "
                "be saved."
            )
        )


    # ------------------------------------------------------
    # 11. Create review case
    # ------------------------------------------------------

    review_case = None


    if (
        decision["action"]
        ==
        "REVIEW"
    ):

        review_case = (
            live_store.create_review_case({

                "case_id":
                    (
                        f"CASE-"
                        f"{uuid.uuid4().hex[:8].upper()}"
                    ),

                "transaction_id":
                    transaction.transaction_id,

                "risk_score":
                    risk_score,

                "regional_risk":
                    regional_risk,

                "reasons":
                    decision["reasons"],

                "created_at":
                    event_time,

            })
        )


    # ------------------------------------------------------
    # 12. Audit record
    # ------------------------------------------------------

    audit_record = {

        "timestamp":
            event_time,

        "transaction_id":
            transaction.transaction_id,

        "risk_probability":
            risk_probability,

        "risk_score":
            risk_score,

        "regional_risk":
            regional_risk,

        "recommended_action":
            decision["action"],

        "final_action":
            (
                "PENDING_REVIEW"
                if decision["action"]
                ==
                "REVIEW"

                else
                decision["action"]
            ),

        "reasons":
            decision["reasons"],

        "reviewer":
            None,
    }


    live_store.save_audit(
        audit_record
    )


    # ------------------------------------------------------
    # 13. Response
    # ------------------------------------------------------

    return {

        "transaction_id":
            transaction.transaction_id,

        "risk":
            risk,

        "regional_context": {

            "region_key":
                region_key,

            "historical_transactions":
                baseline_count,

            "historical_avg_risk":
                round(
                    baseline_avg_risk,
                    2
                ),

            "regional_risk":
                round(
                    regional_risk,
                    2
                ),
        },

        "policy":
            current_policy,

        "decision":
            decision,

        "review_case":
            review_case,

        "feature_source":
            (
                "simulator_template"
                if source.startswith(
                    "simulator_"
                )
                else source
            ),

        "audit":
            audit_record,
    }


# ==========================================================
# REVIEWS
# ==========================================================

@app.get("/api/reviews")
def get_reviews(
    status: str | None = None
):

    return {

        "reviews":
            live_store.review_cases(
                status
            )

    }


@app.post("/api/reviews/{case_id}/resolve")
def resolve_review(

    case_id: str,

    resolution: str,

    reviewer: str = "analyst",

    notes: str = ""
):

    # ------------------------------------------------------
    # Validate resolution
    # ------------------------------------------------------

    allowed_resolutions = {

        "APPROVE",

        "DECLINE",

        "BLOCK",

        "ESCALATE",

    }


    resolution = (
        resolution
        .upper()
        .strip()
    )


    if (
        resolution
        not in
        allowed_resolutions
    ):

        raise HTTPException(

            status_code=400,

            detail=(
                "resolution must be "
                "APPROVE, DECLINE, "
                "BLOCK, or ESCALATE"
            ),

        )


    # ------------------------------------------------------
    # Find case
    # ------------------------------------------------------

    case = (
        live_store.get_review_case(
            case_id
        )
    )


    if case is None:

        raise HTTPException(

            status_code=404,

            detail=
                "Review case not found",

        )


    # ------------------------------------------------------
    # Resolve case
    # ------------------------------------------------------

    result = (
        live_store.resolve_review(

            case_id=
                case_id,

            resolution=
                resolution,

            reviewer=
                reviewer,

            notes=
                notes,

        )
    )


    if result is None:

        raise HTTPException(

            status_code=500,

            detail=
                "Unable to resolve review case",

        )


    # ------------------------------------------------------
    # Human decision audit
    # ------------------------------------------------------

    risk_score = float(

        result.get(
            "risk_score",
            0
        )

    )


    risk_probability = float(

        result.get(

            "risk_probability",

            risk_score / 100.0,

        )

    )


    regional_risk = float(

        result.get(

            "regional_risk",

            0,

        )

    )


    live_store.save_audit({

        "timestamp":
            result["resolved_at"],

        "transaction_id":
            result["transaction_id"],

        "risk_probability":
            round(
                risk_probability,
                6
            ),

        "risk_score":
            round(
                risk_score,
                2
            ),

        "regional_risk":
            round(
                regional_risk,
                2
            ),

        "recommended_action":
            "REVIEW",

        "final_action":
            resolution,

        "reasons":
            result.get(
                "reasons",
                []
            ),

        "reviewer":
            reviewer,

    })


    return result


# ==========================================================
# DASHBOARD
# ==========================================================

@app.get("/api/dashboard/stats")
def dashboard_stats():

    return live_store.stats()


# ==========================================================
# RECENT TRANSACTIONS
# ==========================================================

@app.get("/api/transactions/recent")
def recent_transactions(
    limit: int = 50
):

    limit = max(
        1,
        min(
            limit,
            200
        )
    )


    transactions = (
        live_store.recent_transactions(
            limit
        )
    )


    return {

        "count":
            len(transactions),

        "transactions":
            transactions,

    }


# ==========================================================
# AUDIT
# ==========================================================

@app.get("/api/audit")
def get_audit():

    return {

        "audit":
            live_store.audit_records()

    }


# ==========================================================
# POLICY
# ==========================================================

@app.get("/api/policy")
def get_policy():

    return {

        "policy":
            live_store.get_policy()

    }


@app.put("/api/policy")
def update_policy(
    policy: PolicyUpdateRequest
):

    if (
        policy.allow_threshold
        >=
        policy.block_threshold
    ):

        raise HTTPException(

            status_code=400,

            detail=(
                "Allow threshold must be "
                "lower than block threshold."
            ),

        )


    try:

        updated = (
            live_store.update_policy(

                allow_threshold=
                    policy.allow_threshold,

                block_threshold=
                    policy.block_threshold,

            )
        )

    except ValueError as exc:

        raise HTTPException(

            status_code=400,

            detail=str(exc),

        )


    return {

        "status":
            "updated",

        "policy":
            updated,

    }

# ==========================================================
# LIVE ANOMALY HELPERS
# ==========================================================

def _live_transactions(limit: int = 500):
    """
    Read the latest transactions from the live SQLite store.
    """
    try:
        return live_store.recent_transactions(limit)
    except Exception:
        return []


def _parse_event_time(value):
    """
    Convert stored ISO timestamp to UTC datetime.
    """
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _five_minute_bin(value):
    """
    Put an event into a 5-minute time bucket.
    """
    dt = _parse_event_time(value)

    epoch_minutes = int(
        dt.timestamp() // 300
    )

    return epoch_minutes


def _severity_from_z(z_score):
    if z_score >= 4.0:
        return "CRITICAL"

    if z_score >= 3.0:
        return "HIGH"

    if z_score >= 2.0:
        return "MEDIUM"

    return "LOW"


def _build_live_spikes():
    """
    Detect live global fraud/risk spikes from recently
    submitted transactions.

    This is intentionally separate from the historical
    spike_engine so the UI can demonstrate live behaviour.
    """

    transactions = _live_transactions(500)

    if len(transactions) < 2:
        return []


    risks = [
        float(tx.get("risk_score", 0))
        for tx in transactions
    ]

    high_flags = [
        1 if float(
            tx.get("risk_score", 0)
        ) >= 76 else 0

        for tx in transactions
    ]


    overall_avg = mean(risks)

    overall_high_rate = (
        sum(high_flags) /
        len(high_flags)
    )


    grouped = defaultdict(list)


    for tx in transactions:

        bucket = _five_minute_bin(
            tx.get("event_time")
        )

        grouped[bucket].append(
            tx
        )


    results = []


    for time_bin, items in grouped.items():

        if len(items) < 2:
            continue


        bin_risks = [
            float(
                item.get(
                    "risk_score",
                    0
                )
            )
            for item in items
        ]


        bin_high_rate = (
            sum(
                1
                for risk in bin_risks
                if risk >= 76
            )
            /
            len(bin_risks)
        )


        bin_avg_risk = mean(
            bin_risks
        )


        # -----------------------------------------------
        # Statistical score based on high-risk rate
        # -----------------------------------------------

        variance = (
            overall_high_rate
            *
            (1 - overall_high_rate)
            /
            max(
                len(items),
                1
            )
        )


        if variance > 0:

            z_score = (
                bin_high_rate
                -
                overall_high_rate
            ) / (
                variance ** 0.5
            )

        else:

            z_score = (
                4.0
                if bin_high_rate > overall_high_rate
                else 0.0
            )


        # -----------------------------------------------
        # Risk-level reinforcement
        # -----------------------------------------------

        risk_shift = (
            bin_avg_risk -
            overall_avg
        )


        if risk_shift > 15:

            z_score = max(
                z_score,
                3.0
            )


        if (
            bin_high_rate >= 0.50
            and
            bin_avg_risk >= 58
        ):

            z_score = max(
                z_score,
                3.0
            )


        if z_score < 2.0:
            continue


        severity = _severity_from_z(
            z_score
        )


        # Convert the difference into a rate increase
        rate_increase = (
            bin_high_rate -
            overall_high_rate
        )


        results.append({

            "time_bin":
                time_bin,

            "transactions":
                len(items),

            "avg_risk":
                round(
                    bin_avg_risk,
                    2
                ),

            "high_risk_rate":
                round(
                    bin_high_rate,
                    6
                ),

            "rate_increase":
                round(
                    rate_increase,
                    6
                ),

            "z_score":
                round(
                    float(z_score),
                    4
                ),

            "severity":
                severity,

            "source":
                "LIVE_TRANSACTION_STREAM",

        })


    results.sort(
        key=lambda item:
            item["z_score"],
        reverse=True
    )


    return results[:12]


def _build_live_regional_anomalies():
    """
    Detect live regional anomaly windows.

    Compares the newest 5-minute window for each region
    against earlier transactions from the same region.
    """

    transactions = _live_transactions(500)

    if not transactions:
        return []


    by_region = defaultdict(list)


    for tx in transactions:

        region = (
            tx.get("region_key")
            or
            tx.get("region")
            or
            "UNKNOWN"
        )

        by_region[
            str(region)
        ].append(tx)


    results = []


    for region, region_txs in by_region.items():

        if len(region_txs) < 3:
            continue


        ordered = sorted(
            region_txs,
            key=lambda tx:
                _parse_event_time(
                    tx.get("event_time")
                )
        )


        latest_bin = _five_minute_bin(
            ordered[-1].get(
                "event_time"
            )
        )


        current = [
            tx
            for tx in ordered
            if _five_minute_bin(
                tx.get("event_time")
            )
            == latest_bin
        ]


        baseline = [
            tx
            for tx in ordered
            if _five_minute_bin(
                tx.get("event_time")
            )
            != latest_bin
        ]


        if len(current) < 2:
            continue


        # Not enough historical regional data
        # means we do not claim an anomaly.
        if len(baseline) < 1:
            continue


        current_risks = [
            float(
                tx.get(
                    "risk_score",
                    0
                )
            )
            for tx in current
        ]


        baseline_risks = [
            float(
                tx.get(
                    "risk_score",
                    0
                )
            )
            for tx in baseline
        ]


        current_avg = mean(
            current_risks
        )


        baseline_avg = mean(
            baseline_risks
        )


        current_high_rate = (
            sum(
                1
                for risk in current_risks
                if risk >= 76
            )
            /
            len(current_risks)
        )


        baseline_high_rate = (
            sum(
                1
                for risk in baseline_risks
                if risk >= 76
            )
            /
            len(baseline_risks)
        )


        avg_shift = (
            current_avg -
            baseline_avg
        )


        rate_shift = (
            current_high_rate -
            baseline_high_rate
        )


        # -----------------------------------------------
        # Live anomaly score
        # -----------------------------------------------

        anomaly_score = max(
            0.0,
            min(
                100.0,
                (
                    max(
                        0.0,
                        avg_shift
                    )
                    * 3
                )
                +
                (
                    max(
                        0.0,
                        rate_shift
                    )
                    * 100
                )
            )
        )


        # Strong risk cluster can trigger an anomaly
        if (
            current_avg >= 70
            and
            len(current) >= 2
        ):
            anomaly_score = max(
                anomaly_score,
                70.0
            )


        if anomaly_score < 50:
            continue


        # -----------------------------------------------
        # Z-like deviation
        # -----------------------------------------------

        base_std = pstdev(
            baseline_risks
        )


        if base_std > 0:

            z_score = (
                current_avg -
                baseline_avg
            ) / base_std

        else:

            z_score = (
                4.0
                if current_avg >
                baseline_avg
                else
                0.0
            )


        severity = (
            "CRITICAL"
            if anomaly_score >= 85
            else
            "HIGH"
            if anomaly_score >= 65
            else
            "MEDIUM"
        )


        results.append({

            "time_bin":
                latest_bin,

            "region_key":
                region,

            "transactions":
                len(current),

            "baseline_avg_risk":
                round(
                    baseline_avg,
                    2
                ),

            "current_avg_risk":
                round(
                    current_avg,
                    2
                ),

            "baseline_high_risk_rate":
                round(
                    baseline_high_rate,
                    6
                ),

            "current_high_risk_rate":
                round(
                    current_high_rate,
                    6
                ),

            "regional_anomaly_score":
                round(
                    anomaly_score,
                    2
                ),

            "z_score":
                round(
                    float(z_score),
                    4
                ),

            "severity":
                severity,

            "source":
                "LIVE_TRANSACTION_STREAM",

        })


    results.sort(
        key=lambda item:
            item[
                "regional_anomaly_score"
            ],
        reverse=True
    )


    return results[:12]


def _build_live_incident():

    anomalies = (
        _build_live_regional_anomalies()
    )


    if not anomalies:
        return None


    anomaly = anomalies[0]


    region = anomaly[
        "region_key"
    ]


    transactions = [
        tx
        for tx in _live_transactions(500)
        if str(
            tx.get(
                "region_key",
                "UNKNOWN"
            )
        )
        ==
        str(region)
    ]


    if not transactions:
        return None


    current_rate = float(
        anomaly[
            "current_high_risk_rate"
        ]
    )


    baseline_rate = float(
        anomaly[
            "baseline_high_risk_rate"
        ]
    )


    rate_ratio = (
        current_rate /
        baseline_rate
        if baseline_rate > 0
        else
        (
            100.0
            if current_rate > 0
            else 1.0
        )
    )


    risk_scores = [
        float(
            tx.get(
                "risk_score",
                0
            )
        )
        for tx in transactions
    ]


    amounts = [
        float(
            tx.get(
                "amount",
                0
            )
        )
        for tx in transactions
    ]


    affected = len(
        transactions
    )


    average_risk = mean(
        risk_scores
    )


    exposure = sum(
        amount
        for amount in amounts
        if amount > 0
    )


    incident_id = (
        "INC-LIVE-"
        +
        str(region)
            .replace(" ", "_")
            .replace("/", "_")
            .replace(".", "_")
    )


    incident = {

        "incident_id":
            incident_id,

        "incident_type":
            "LIVE_REGIONAL_RISK_SPIKE",

        "severity":
            anomaly["severity"],

        "status":
            "OPEN",

        "region":
            str(region),

        "region_key":
            str(region),

        "affected":
            affected,

        "affected_transactions":
            affected,

        "z_score":
            round(
                float(
                    anomaly["z_score"]
                ),
                2
            ),

        "rate_ratio":
            round(
                rate_ratio,
                2
            ),

        "baseline_rate":
            round(
                baseline_rate * 100,
                2
            ),

        "current_rate":
            round(
                current_rate * 100,
                2
            ),

        "baseline_avg_risk":
            round(
                float(
                    anomaly[
                        "baseline_avg_risk"
                    ]
                ),
                2
            ),

        "current_avg_risk":
            round(
                float(
                    anomaly[
                        "current_avg_risk"
                    ]
                ),
                2
            ),

        "average_risk":
            round(
                average_risk,
                2
            ),

        "exposure":
            round(
                exposure,
                2
            ),

        "source":
            "LIVE_TRANSACTION_STREAM",

        "description":
            (
                "Live regional risk spike detected "
                "from newly submitted transactions."
            ),

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "message":
            (
                f"Regional activity in {region} "
                "is significantly above its recent baseline."
            ),

    }


    return incident


def _live_incident_graph():

    incident = _build_live_incident()

    if incident is None:
        return {
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
        }


    region = incident[
        "region_key"
    ]


    txs = [
        tx
        for tx in _live_transactions(200)
        if str(
            tx.get(
                "region_key",
                "UNKNOWN"
            )
        )
        ==
        str(region)
    ][:12]


    nodes = []


    region_node = {
        "node_id":
            f"region_{region}",
        "node_type":
            "region",
        "label":
            str(region),
        "cluster_id":
            None,
        "transaction_count":
            len(txs),
    }


    nodes.append(
        region_node
    )


    edges = []


    devices = {}
    payments = {}


    for index, tx in enumerate(
        txs,
        start=1
    ):

        tx_id = (
            f"live_tx_{index}"
        )


        device_value = (
            tx.get("device_id")
            or
            f"DEVICE-{index}"
        )


        payment_value = (
            tx.get("payment_method")
            or
            "card"
        )


        payment_key = str(
            payment_value
        )


        device_key = str(
            device_value
        )


        if device_key not in devices:

            devices[
                device_key
            ] = (
                f"live_device_{len(devices)+1}"
            )


            nodes.append({

                "node_id":
                    devices[
                        device_key
                    ],

                "node_type":
                    "device",

                "label":
                    device_key,

                "cluster_id":
                    None,

                "transaction_count":
                    0,

            })


        if payment_key not in payments:

            payments[
                payment_key
            ] = (
                f"live_payment_{len(payments)+1}"
            )


            nodes.append({

                "node_id":
                    payments[
                        payment_key
                    ],

                "node_type":
                    "payment",

                "label":
                    payment_key,

                "cluster_id":
                    None,

                "transaction_count":
                    0,

            })


        # Transaction node
        nodes.append({

            "node_id":
                tx_id,

            "node_type":
                "transaction",

            "label":
                str(
                    tx.get(
                        "transaction_id",
                        tx_id
                    )
                ),

            "cluster_id":
                None,

            "transaction_count":
                1,

        })


        devices[
            device_key
        ]


        payments[
            payment_key
        ]


        edges.append({

            "source_node":
                devices[
                    device_key
                ],

            "target_node":
                f"region_{region}",

            "edge_type":
                "device_region",

        })


        edges.append({

            "source_node":
                payments[
                    payment_key
                ],

            "target_node":
                f"region_{region}",

            "edge_type":
                "payment_region",

        })


        edges.append({

            "source_node":
                tx_id,

            "target_node":
                devices[
                    device_key
                ],

            "edge_type":
                "transaction_device",

        })


        edges.append({

            "source_node":
                tx_id,

            "target_node":
                payments[
                    payment_key
                ],

            "edge_type":
                "transaction_payment",

        })


    return {

        "nodes":
            nodes,

        "edges":
            edges,

        "device_clusters":
            len(devices),

        "payment_clusters":
            len(payments),

        "transaction_nodes":
            len(txs),

        "total_nodes":
            len(nodes),

        "total_edges":
            len(edges),

        "source":
            "LIVE_TRANSACTION_STREAM",

    }


def _live_incident_devices():

    incident = _build_live_incident()

    if incident is None:
        return []


    region = incident[
        "region_key"
    ]


    txs = [
        tx
        for tx in _live_transactions(200)
        if str(
            tx.get(
                "region_key",
                "UNKNOWN"
            )
        )
        ==
        str(region)
    ]


    groups = defaultdict(int)


    for tx in txs:

        device = (
            tx.get(
                "device_id"
            )
            or
            "UNKNOWN_DEVICE"
        )


        groups[
            str(device)
        ] += 1


    return [

        {
            "node_id":
                f"live_device_{index}",

            "label":
                device,

            "transaction_count":
                count,

        }

        for index, (
            device,
            count
        )
        in enumerate(
            groups.items(),
            start=1
        )

    ]


def _live_incident_payments():

    incident = _build_live_incident()

    if incident is None:
        return []


    region = incident[
        "region_key"
    ]


    txs = [
        tx
        for tx in _live_transactions(200)
        if str(
            tx.get(
                "region_key",
                "UNKNOWN"
            )
        )
        ==
        str(region)
    ]


    groups = defaultdict(int)


    for tx in txs:

        payment = (
            tx.get(
                "payment_method"
            )
            or
            "unknown"
        )


        groups[
            str(payment)
        ] += 1


    return [

        {
            "node_id":
                f"live_payment_{index}",

            "label":
                payment,

            "transaction_count":
                count,

        }

        for index, (
            payment,
            count
        )
        in enumerate(
            groups.items(),
            start=1
        )

    ]


# ==========================================================
# LIVE INCIDENT DETECTION
# ==========================================================

def build_live_incidents():

    transactions = (
        live_store.recent_transactions(500)
    )

    if not transactions:
        return []


    # Group transactions by region
    regions = {}

    for tx in transactions:

        region = (
            tx.get("region_key")
            or
            tx.get("region")
            or
            "UNKNOWN"
        )

        region = str(region)

        regions.setdefault(
            region,
            []
        ).append(tx)


    incidents = []


    for region, region_transactions in regions.items():

        risks = [

            float(
                tx.get(
                    "risk_score",
                    0
                )
            )

            for tx in region_transactions
        ]


        high_risk_transactions = [

            tx

            for tx in region_transactions

            if float(
                tx.get(
                    "risk_score",
                    0
                )
            ) >= 76

        ]


        average_risk = (
            sum(risks) /
            len(risks)
            if risks
            else 0
        )


        # Detect a live regional incident when:
        #
        # 2+ high-risk transactions
        # OR
        # 3+ transactions with average risk >= 58

        triggered = (

            len(
                high_risk_transactions
            ) >= 2

            or

            (
                len(region_transactions) >= 3
                and
                average_risk >= 58
            )

        )


        if not triggered:
            continue


        amounts = [

            float(
                tx.get(
                    "amount",
                    0
                )
            )

            for tx in region_transactions

        ]


        exposure = sum(
            amounts
        )


        current_rate = (

            len(
                high_risk_transactions
            )
            /
            len(region_transactions)

            if region_transactions
            else 0

        )


        # Simple live anomaly score
        anomaly_score = min(
            100,
            (
                average_risk * 0.7
                +
                current_rate * 30
            )
        )


        if anomaly_score >= 85:

            severity = "CRITICAL"

        elif anomaly_score >= 65:

            severity = "HIGH"

        else:

            severity = "MEDIUM"


        incident_id = (

            "INC-LIVE-"

            +

            region
                .upper()
                .replace(" ", "_")
                .replace("/", "_")
                .replace(".", "_")
                .replace("-", "_")

        )


        # ------------------------------------------------------
        # Stable incident metrics expected by the UI
        # ------------------------------------------------------

        # Use a small baseline high-risk rate so the UI can
        # display a meaningful live comparison without NaN.
        baseline_rate = 0.05

        current_rate_decimal = (
            len(high_risk_transactions)
            /
            len(region_transactions)
            if region_transactions
            else 0.0
        )

        rate_ratio = (
            current_rate_decimal / baseline_rate
            if baseline_rate > 0
            else 0.0
        )

        z_score = max(
            0.0,
            (
                average_risk - 50.0
            ) / 10.0
        )

        def _event_bin(tx):
            try:
                dt = datetime.fromisoformat(
                    str(
                        tx.get(
                            "event_time"
                        )
                    ).replace(
                        "Z",
                        "+00:00"
                    )
                ).astimezone(
                    timezone.utc
                )
                return int(
                    dt.timestamp() // 300
                )
            except Exception:
                return 0

        bins = [
            _event_bin(tx)
            for tx in region_transactions
        ]

        start_bin = min(
            bins
        ) if bins else 0

        end_bin = max(
            bins
        ) if bins else start_bin

        incidents.append({

            "incident_id":
                incident_id,

            "incident_type":
                "LIVE_REGIONAL_RISK_SPIKE",

            "severity":
                severity,

            "status":
                "OPEN",

            "region":
                region,

            "region_key":
                region,

            "affected":
                len(
                    region_transactions
                ),

            "affected_transactions":
                len(
                    region_transactions
                ),

            "high_risk_transactions":
                len(
                    high_risk_transactions
                ),

            "baseline_rate":
                round(
                    baseline_rate,
                    4
                ),

            "current_rate":
                round(
                    current_rate_decimal,
                    4
                ),

            "baseline":
                round(
                    baseline_rate * 100,
                    2
                ),

            "current":
                round(
                    current_rate_decimal * 100,
                    2
                ),

            "z_score":
                round(
                    z_score,
                    2
                ),

            "rate_ratio":
                round(
                    rate_ratio,
                    2
                ),

            "exposure":
                round(
                    exposure,
                    2
                ),

            "start_bin":
                start_bin,

            "end_bin":
                end_bin,

            "average_risk":
                round(
                    average_risk,
                    2
                ),

            "source":
                "LIVE_TRANSACTION_STREAM",

            "description":
                (
                    "Live regional risk activity "
                    "detected from recently submitted "
                    "transactions."
                ),

            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "transactions":
                [
                    tx.get(
                        "transaction_id"
                    )

                    for tx in
                    region_transactions
                ]

        })


    return incidents


# ==========================================================
# INCIDENTS
# ==========================================================

@app.get("/api/incidents")
def get_incidents():

    # Existing seeded incidents
    try:

        historical_incidents = (
            incident_engine.list_incidents()
        )

    except Exception:

        historical_incidents = []


    # New live incidents
    live_incidents = (
        build_live_incidents()
    )


    return {

        "incidents":
            historical_incidents
            +
            live_incidents

    }


@app.get("/api/incidents/stats")
def get_incident_stats():

    try:

        historical_incidents = (
            incident_engine.list_incidents()
        )

    except Exception:

        historical_incidents = []


    live_incidents = (
        build_live_incidents()
    )


    incidents = (
        historical_incidents
        +
        live_incidents
    )


    return {

        "open_incidents":
            sum(
                1
                for incident in incidents
                if incident.get(
                    "status"
                )
                == "OPEN"
            ),

        "critical_incidents":
            sum(
                1
                for incident in incidents
                if incident.get(
                    "severity"
                )
                == "CRITICAL"
            ),

        "affected_transactions":
            sum(
                int(
                    incident.get(
                        "affected_transactions",
                        incident.get(
                            "affected",
                            0
                        )
                    )
                )

                for incident in incidents
            ),

        "total_incidents":
            len(incidents)

    }


@app.get("/api/incidents/{incident_id}")
def get_incident(
    incident_id: str
):

    live_incidents = (
        build_live_incidents()
    )


    for incident in live_incidents:

        if (
            incident.get(
                "incident_id"
            )
            ==
            incident_id
        ):

            return incident


    try:

        incident = (
            incident_engine.get_incident(
                incident_id
            )
        )

    except Exception:

        incident = None


    if incident is None:

        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )


    return incident


@app.get("/api/incidents/{incident_id}/graph")
def get_incident_graph(
    incident_id: str
):

    live_incidents = (
        build_live_incidents()
    )


    for incident in live_incidents:

        if (
            incident.get(
                "incident_id"
            )
            ==
            incident_id
        ):

            region = incident[
                "region_key"
            ]


            region_transactions = [

                tx

                for tx in
                live_store.recent_transactions(
                    200
                )

                if str(
                    tx.get(
                        "region_key",
                        "UNKNOWN"
                    )
                )
                ==
                str(region)

            ]


            nodes = []

            edges = []


            # Region node
            region_node = (
                f"region_{region}"
            )


            nodes.append({

                "node_id":
                    region_node,

                "node_type":
                    "region",

                "label":
                    region,

                "cluster_id":
                    None,

                "transaction_count":
                    len(
                        region_transactions
                    )

            })


            device_nodes = {}
            payment_nodes = {}


            for index, tx in enumerate(
                region_transactions,
                start=1
            ):

                tx_node = (
                    f"live_tx_{index}"
                )


                device = (

                    str(
                        tx.get(
                            "device_id"
                        )
                    )

                    if tx.get(
                        "device_id"
                    )

                    else
                    f"DEVICE-{index}"

                )


                payment = (

                    str(
                        tx.get(
                            "payment_method"
                        )
                    )

                    if tx.get(
                        "payment_method"
                    )

                    else
                    "card"

                )


                if device not in device_nodes:

                    device_nodes[
                        device
                    ] = (
                        f"device_{len(device_nodes)+1}"
                    )


                    nodes.append({

                        "node_id":
                            device_nodes[
                                device
                            ],

                        "node_type":
                            "device",

                        "label":
                            device,

                        "cluster_id":
                            None,

                        "transaction_count":
                            0

                    })


                if payment not in payment_nodes:

                    payment_nodes[
                        payment
                    ] = (
                        f"payment_{len(payment_nodes)+1}"
                    )


                    nodes.append({

                        "node_id":
                            payment_nodes[
                                payment
                            ],

                        "node_type":
                            "payment",

                        "label":
                            payment,

                        "cluster_id":
                            None,

                        "transaction_count":
                            0

                    })


                nodes.append({

                    "node_id":
                        tx_node,

                    "node_type":
                        "transaction",

                    "label":
                        str(
                            tx.get(
                                "transaction_id"
                            )
                        ),

                    "cluster_id":
                        None,

                    "transaction_count":
                        1

                })


                edges.append({

                    "source_node":
                        tx_node,

                    "target_node":
                        device_nodes[
                            device
                        ],

                    "edge_type":
                        "transaction_device"

                })


                edges.append({

                    "source_node":
                        tx_node,

                    "target_node":
                        payment_nodes[
                            payment
                        ],

                    "edge_type":
                        "transaction_payment"

                })


                edges.append({

                    "source_node":
                        device_nodes[
                            device
                        ],

                    "target_node":
                        region_node,

                    "edge_type":
                        "device_region"

                })


                edges.append({

                    "source_node":
                        payment_nodes[
                            payment
                        ],

                    "target_node":
                        region_node,

                    "edge_type":
                        "payment_region"

                })


            return {

                "nodes":
                    nodes,

                "edges":
                    edges,

                "device_clusters":
                    len(
                        device_nodes
                    ),

                "payment_clusters":
                    len(
                        payment_nodes
                    ),

                "transaction_nodes":
                    len(
                        region_transactions
                    ),

                "total_nodes":
                    len(nodes),

                "total_edges":
                    len(edges),

                "source":
                    "LIVE_TRANSACTION_STREAM"

            }


    try:

        incident = (
            incident_engine.get_incident(
                incident_id
            )
        )

    except Exception:

        incident = None


    if incident is None:

        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )


    return (
        incident_engine.get_graph(
            incident_id
        )
    )

# ==========================================================
# FRAUD SPIKES
# ==========================================================

@app.get("/api/spikes")
def get_spikes():

    live_spikes = (
        _build_live_spikes()
    )


    regional_anomalies = (
        _build_live_regional_anomalies()
    )


    return {

        "spikes":
            live_spikes,

        "regional_anomaly_windows":
            regional_anomalies,

        # aliases for compatibility
        "regional_anomalies":
            regional_anomalies,

        "source":
            "LIVE_TRANSACTION_STREAM",

    }


@app.get("/api/spikes/summary")
def get_spike_summary():

    spikes = (
        _build_live_spikes()
    )


    regional = (
        _build_live_regional_anomalies()
    )


    high = sum(
        1
        for spike in spikes
        if spike.get("severity")
        in {
            "HIGH",
            "CRITICAL"
        }
    )


    medium = sum(
        1
        for spike in spikes
        if spike.get("severity")
        ==
        "MEDIUM"
    )


    maximum_z = max(
        (
            float(
                spike.get(
                    "z_score",
                    0
                )
            )
            for spike in spikes
        ),
        default=0
    )


    return {

        "confirmed_spikes":
            len(spikes),

        "high_severity":
            high,

        "medium_severity":
            medium,

        "maximum_z_score":
            round(
                maximum_z,
                2
            ),

        "regional_anomalies":
            len(regional),

        "regional_anomaly_windows":
            len(regional),

        "source":
            "LIVE_TRANSACTION_STREAM",

    }