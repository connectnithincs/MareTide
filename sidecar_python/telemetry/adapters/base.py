"""
Base Telemetry Adapter Interface for MareTide.
Provides an abstract contract that all telemetry sources (Hardware UART, Simulator, Derived)
must implement, completely decoupling the stability engine from raw physical hardware.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from telemetry.models import TelemetrySource, ConnectionStatus


class BaseTelemetryAdapter(ABC):
    """
    Abstract Base Class for Telemetry Adapters.
    """

    def __init__(self, adapter_id: str, source_type: TelemetrySource):
        self.adapter_id = adapter_id
        self.source_type = source_type
        self.is_simulated = (source_type in [TelemetrySource.SIMULATED_TELEMETRY, TelemetrySource.SIMULATED_ESP32])

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection to the underlying telemetry source."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Terminates connection to the telemetry source and cleans up resources."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if the underlying source is currently connected and active."""
        pass

    @abstractmethod
    def read_raw(self) -> Optional[Dict[str, Any]]:
        """
        Reads the latest raw telemetry packet from the source.
        Returns a dictionary of raw parameters, or None if no packet is available.
        """
        pass

    @abstractmethod
    def send_command(self, command: str, **kwargs) -> bool:
        """
        Sends an operational command to the telemetry source (e.g. 'DRAIN', 'SET_TILT').
        Returns True if command was dispatched successfully.
        """
        pass

    @abstractmethod
    def get_adapter_info(self) -> Dict[str, Any]:
        """Returns status, configuration, and health details about the adapter."""
        pass
