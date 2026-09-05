from typing import Any

from .spike_store import spike_store


class SpikeEngine:

    def __init__(self) -> None:

        print("✅ Fraud spike engine loaded")


    def list_spikes(
        self
    ) -> list[dict[str, Any]]:

        return spike_store.list_spikes()


    def summary(
        self
    ) -> dict[str, Any]:

        return spike_store.summary()


spike_engine = SpikeEngine()