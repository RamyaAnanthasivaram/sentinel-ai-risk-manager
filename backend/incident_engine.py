from typing import Any

from .incident_store import incident_store


class IncidentEngine:

    def __init__(self) -> None:

        print("✅ Incident engine loaded")


    def list_incidents(
        self
    ) -> list[dict[str, Any]]:

        return incident_store.list_incidents()


    def get_incident(
        self,
        incident_id: str
    ) -> dict[str, Any] | None:

        return incident_store.get_incident(
            incident_id
        )


    def stats(
        self
    ) -> dict[str, Any]:

        return incident_store.stats()


    def get_graph(
        self,
        incident_id: str
    ) -> dict[str, Any]:

        return incident_store.get_graph(
            incident_id
        )


    def get_devices(
        self,
        incident_id: str
    ) -> list[dict[str, Any]]:

        return incident_store.get_devices(
            incident_id
        )


    def get_payments(
        self,
        incident_id: str
    ) -> list[dict[str, Any]]:

        return incident_store.get_payments(
            incident_id
        )


incident_engine = IncidentEngine()