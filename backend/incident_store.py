from pathlib import Path
import sqlite3
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "sentinel.db"


class IncidentStore:

    def __init__(self) -> None:

        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self._initialize()

        self._seed_controlled_incident()

        self._seed_controlled_graph()


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
    # TABLES
    # ======================================================

    def _initialize(self) -> None:

        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS incidents (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    incident_id TEXT NOT NULL UNIQUE,

                    incident_type TEXT NOT NULL,

                    severity TEXT NOT NULL,

                    status TEXT NOT NULL,

                    region_key TEXT,

                    start_time_bin INTEGER,

                    end_time_bin INTEGER,

                    affected_transactions INTEGER,

                    baseline_rate REAL,

                    current_rate REAL,

                    z_score REAL,

                    rate_ratio REAL,

                    total_exposure REAL DEFAULT 0,

                    source TEXT NOT NULL,

                    description TEXT,

                    created_at TEXT NOT NULL
                )
            """)


            connection.execute("""
                CREATE TABLE IF NOT EXISTS incident_nodes (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    incident_id TEXT NOT NULL,

                    node_id TEXT NOT NULL,

                    node_type TEXT NOT NULL,

                    label TEXT NOT NULL,

                    cluster_id TEXT,

                    transaction_count INTEGER DEFAULT 0,

                    UNIQUE (
                        incident_id,
                        node_id
                    )
                )
            """)


            connection.execute("""
                CREATE TABLE IF NOT EXISTS incident_edges (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    incident_id TEXT NOT NULL,

                    source_node TEXT NOT NULL,

                    target_node TEXT NOT NULL,

                    edge_type TEXT NOT NULL,

                    UNIQUE (
                        incident_id,
                        source_node,
                        target_node,
                        edge_type
                    )
                )
            """)


    # ======================================================
    # INCIDENT
    # ======================================================

    def _seed_controlled_incident(self) -> None:

        with self._connect() as connection:

            existing = connection.execute("""
                SELECT 1
                FROM incidents
                WHERE incident_id = ?
            """, (
                "INC-0001",
            )).fetchone()


            if existing:
                return


            connection.execute("""
                INSERT INTO incidents (

                    incident_id,
                    incident_type,
                    severity,
                    status,
                    region_key,
                    start_time_bin,
                    end_time_bin,
                    affected_transactions,
                    baseline_rate,
                    current_rate,
                    z_score,
                    rate_ratio,
                    total_exposure,
                    source,
                    description,
                    created_at

                )

                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
            """, (

                "INC-0001",

                "REGIONAL_RISK_SPIKE",

                "CRITICAL",

                "OPEN",

                "299.0_87.0",

                8784,

                8785,

                150,

                0.037438,

                1.0,

                47.782762,

                26.710511,

                22835.16,

                "CONTROLLED_SIMULATION",

                (
                    "Controlled regional attack stress test "
                    "detected by Sentinel."
                ),

                "2026-09-04T09:00:00+00:00"
            ))


    # ======================================================
    # GRAPH
    # ======================================================

    def _seed_controlled_graph(self) -> None:

        with self._connect() as connection:

            existing = connection.execute("""
                SELECT 1
                FROM incident_nodes
                WHERE incident_id = ?
                LIMIT 1
            """, (
                "INC-0001",
            )).fetchone()


            if existing:
                return


            incident_id = "INC-0001"

            region = "region_299_87"

            connection.execute("""
                INSERT INTO incident_nodes
                (
                    incident_id,
                    node_id,
                    node_type,
                    label,
                    cluster_id,
                    transaction_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                incident_id,
                region,
                "region",
                "299.0_87.0",
                None,
                150
            ))


            # ------------------------------------------------
            # 5 device clusters
            # ------------------------------------------------

            for number in range(1, 6):

                device_id = (
                    f"device_cluster_{number}"
                )

                connection.execute("""
                    INSERT INTO incident_nodes
                    (
                        incident_id,
                        node_id,
                        node_type,
                        label,
                        cluster_id,
                        transaction_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    incident_id,
                    device_id,
                    "device",
                    f"ATTACK_DEVICE_{number}",
                    f"D{number}",
                    30
                ))


                connection.execute("""
                    INSERT INTO incident_edges
                    (
                        incident_id,
                        source_node,
                        target_node,
                        edge_type
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    incident_id,
                    device_id,
                    region,
                    "device_region"
                ))


            # ------------------------------------------------
            # 8 payment clusters
            # ------------------------------------------------

            payment_counts = [
                19, 19, 19, 19,
                19, 19, 18, 18
            ]


            for index, count in enumerate(
                payment_counts,
                start=1
            ):

                payment_id = (
                    f"payment_cluster_{index}"
                )

                connection.execute("""
                    INSERT INTO incident_nodes
                    (
                        incident_id,
                        node_id,
                        node_type,
                        label,
                        cluster_id,
                        transaction_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    incident_id,
                    payment_id,
                    "payment",
                    f"ATTACK_CARD_{index}",
                    f"P{index}",
                    count
                ))


                connection.execute("""
                    INSERT INTO incident_edges
                    (
                        incident_id,
                        source_node,
                        target_node,
                        edge_type
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    incident_id,
                    payment_id,
                    region,
                    "payment_region"
                ))


            # ------------------------------------------------
            # Transaction nodes
            #
            # We store representative transaction nodes here
            # for visualization. The incident itself represents
            # all 150 affected transactions.
            # ------------------------------------------------

            for number in range(1, 11):

                transaction_id = (
                    f"tx_cluster_{number}"
                )

                connection.execute("""
                    INSERT INTO incident_nodes
                    (
                        incident_id,
                        node_id,
                        node_type,
                        label,
                        cluster_id,
                        transaction_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    incident_id,
                    transaction_id,
                    "transaction",
                    f"TX-{number:03d}",
                    None,
                    1
                ))

                # Connect representative TX nodes
                # to a device and payment signal.

                device_number = (
                    ((number - 1) % 5) + 1
                )

                payment_number = (
                    ((number - 1) % 8) + 1
                )

                connection.execute("""
                    INSERT INTO incident_edges
                    (
                        incident_id,
                        source_node,
                        target_node,
                        edge_type
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    incident_id,
                    transaction_id,
                    f"device_cluster_{device_number}",
                    "transaction_device"
                ))

                connection.execute("""
                    INSERT INTO incident_edges
                    (
                        incident_id,
                        source_node,
                        target_node,
                        edge_type
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    incident_id,
                    transaction_id,
                    f"payment_cluster_{payment_number}",
                    "transaction_payment"
                ))


    # ======================================================
    # INCIDENT QUERIES
    # ======================================================

    def list_incidents(
        self
    ) -> list[dict[str, Any]]:

        with self._connect() as connection:

            rows = connection.execute("""
                SELECT *
                FROM incidents
                ORDER BY id DESC
            """).fetchall()


        return [
            dict(row)
            for row in rows
        ]


    def get_incident(
        self,
        incident_id: str
    ) -> dict[str, Any] | None:

        with self._connect() as connection:

            row = connection.execute("""
                SELECT *
                FROM incidents
                WHERE incident_id = ?
            """, (
                incident_id,
            )).fetchone()


        if row is None:

            return None


        return dict(row)


    # ======================================================
    # GRAPH QUERIES
    # ======================================================

    def get_graph(
        self,
        incident_id: str
    ) -> dict[str, Any]:

        with self._connect() as connection:

            nodes = connection.execute("""
                SELECT
                    node_id,
                    node_type,
                    label,
                    cluster_id,
                    transaction_count
                FROM incident_nodes
                WHERE incident_id = ?
                ORDER BY id
            """, (
                incident_id,
            )).fetchall()


            edges = connection.execute("""
                SELECT
                    source_node,
                    target_node,
                    edge_type
                FROM incident_edges
                WHERE incident_id = ?
                ORDER BY id
            """, (
                incident_id,
            )).fetchall()


        node_list = [
            dict(node)
            for node in nodes
        ]

        edge_list = [
            dict(edge)
            for edge in edges
        ]


        devices = [
            node
            for node in node_list
            if node["node_type"] == "device"
        ]


        payments = [
            node
            for node in node_list
            if node["node_type"] == "payment"
        ]


        transactions = [
            node
            for node in node_list
            if node["node_type"] == "transaction"
        ]


        return {

            "nodes": node_list,

            "edges": edge_list,

            "device_clusters":
                len(devices),

            "payment_clusters":
                len(payments),

            "transaction_nodes":
                len(transactions),

            "total_nodes":
                len(node_list),

            "total_edges":
                len(edge_list)
        }


    # ======================================================
    # DEVICE EVIDENCE
    # ======================================================

    def get_devices(
        self,
        incident_id: str
    ) -> list[dict[str, Any]]:

        with self._connect() as connection:

            rows = connection.execute("""
                SELECT
                    node_id,
                    label,
                    cluster_id,
                    transaction_count
                FROM incident_nodes
                WHERE incident_id = ?
                AND node_type = 'device'
                ORDER BY transaction_count DESC
            """, (
                incident_id,
            )).fetchall()


        return [
            dict(row)
            for row in rows
        ]


    # ======================================================
    # PAYMENT EVIDENCE
    # ======================================================

    def get_payments(
        self,
        incident_id: str
    ) -> list[dict[str, Any]]:

        with self._connect() as connection:

            rows = connection.execute("""
                SELECT
                    node_id,
                    label,
                    cluster_id,
                    transaction_count
                FROM incident_nodes
                WHERE incident_id = ?
                AND node_type = 'payment'
                ORDER BY transaction_count DESC
            """, (
                incident_id,
            )).fetchall()


        return [
            dict(row)
            for row in rows
        ]


    # ======================================================
    # INCIDENT STATS
    # ======================================================

    def stats(
        self
    ) -> dict[str, Any]:

        with self._connect() as connection:

            open_count = connection.execute("""
                SELECT COUNT(*)
                FROM incidents
                WHERE status = 'OPEN'
            """).fetchone()[0]


            critical_count = connection.execute("""
                SELECT COUNT(*)
                FROM incidents
                WHERE severity = 'CRITICAL'
                AND status = 'OPEN'
            """).fetchone()[0]


        return {

            "open_incidents":
                int(open_count),

            "critical_incidents":
                int(critical_count)
        }


incident_store = IncidentStore()