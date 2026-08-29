"""
models/ship_profile.py

Represents the ship profile that MareTide attaches to the session.
Updated to read from the sidecar's singleton state manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import sys
import os

@dataclass
class ShipProfile:
    ship_name: str
    imo: str
    total_bays: Optional[int] = None
    tank_capacity: Optional[float] = None
    ship_configuration: Optional[str] = None
    cargo_data: dict = field(default_factory=dict)
    ballast_configuration: dict = field(default_factory=dict)

    @property
    def has_valid_imo(self) -> bool:
        return bool(self.imo) and self.imo.strip().isdigit()


def get_current_ship_profile() -> Optional[ShipProfile]:
    """
    Returns the ShipProfile for the currently logged-in MareTide session.
    Reads dynamically from the sidecar's state singleton.
    """
    # Ensure parent directory is in path to import state.py
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    try:
        from state import get_current_ship
    except ImportError:
        return None

    ship = get_current_ship()
    if not ship:
        return None

    imo = "8735106"  # ALGAMAR IMO for live demo tracking

    return ShipProfile(
        ship_name=ship.name,
        imo=imo,
        total_bays=ship.num_bays,
        tank_capacity=sum(t.capacity for t in ship.tanks.values()),
        ship_configuration="Cargo Vessel",
        cargo_data={"product": "Containers", "quantity_mt": ship.total_cargo_weight()},
        ballast_configuration={"total": ship.total_ballast_weight()},
    )


def seed_demo_ship_profile() -> None:
    pass
