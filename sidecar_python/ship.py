from dataclasses import dataclass, field
from typing import List, Dict, Optional
from digital_twin import DigitalTwin


# -----------------------------
# Container
# -----------------------------
@dataclass
class Container:
    id: str
    weight: float
    bay: int
    side: str          # "port" | "starboard" | "center"
    tier: int = 1      # stack tier (1 = deck level, 2 = second tier, …)


# -----------------------------
# Ballast Tank
# -----------------------------
@dataclass
class BallastTank:
    name: str
    capacity: float
    current_volume: float

    @property
    def fill_ratio(self) -> float:
        if self.capacity == 0:
            return 0.0
        return self.current_volume / self.capacity

    def add_water(self, amount: float) -> float:
        """Returns actual amount added (may be less than requested)."""
        space = self.capacity - self.current_volume
        actual = min(space, amount)
        self.current_volume += actual
        return actual

    def remove_water(self, amount: float) -> float:
        """Returns actual amount removed (may be less than requested)."""
        actual = min(self.current_volume, amount)
        self.current_volume -= actual
        return actual


# -----------------------------
# Ship
# -----------------------------
@dataclass
class Ship:
    name: str
    num_bays: int = 10
    containers: List[Container] = field(default_factory=list)
    tanks: Dict[str, BallastTank] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Cargo helpers
    # ------------------------------------------------------------------
    def slot_occupied(self, bay: int, side: str, tier: int = 1) -> bool:
        return any(
            c.bay == bay and str(c.side).strip().lower() == str(side).strip().lower() and c.tier == tier
            for c in self.containers
        )

    def add_container(self, container: Container) -> bool:
        """
        Returns True on success, False if the slot (bay/side/tier) is taken.
        """
        if self.slot_occupied(container.bay, container.side, container.tier):
            return False
        self.containers.append(container)
        return True

    def remove_container(self, container_id: str) -> Optional[Container]:
        """Remove and return container by id, or None if not found."""
        for i, c in enumerate(self.containers):
            if c.id == container_id:
                return self.containers.pop(i)
        return None

    def total_cargo_weight(self) -> float:
        return sum(c.weight for c in self.containers)

    # ------------------------------------------------------------------
    # Ballast helpers
    # ------------------------------------------------------------------
    def total_ballast_weight(self) -> float:
        return sum(t.current_volume for t in self.tanks.values())

    def ballast_port(self) -> float:
        return sum(
            t.current_volume
            for k, t in self.tanks.items()
            if k.startswith("port")
        )

    def ballast_starboard(self) -> float:
        return sum(
            t.current_volume
            for k, t in self.tanks.items()
            if k.startswith("starboard")
        )

    def pump_ballast(self, from_side: str, to_side: str, amount: float) -> float:
        """
        Transfer ballast between sides.
        Returns the actual amount transferred.
        """
        transferred = 0.0
        for key, tank in self.tanks.items():
            if key.startswith(from_side) and amount > 0:
                removed = tank.remove_water(amount)
                amount -= removed
                transferred += removed

        remaining = transferred
        for key, tank in self.tanks.items():
            if key.startswith(to_side) and remaining > 0:
                added = tank.add_water(remaining)
                remaining -= added

        return transferred


# -----------------------------
# Stability Analyzer
# -----------------------------
class StabilityAnalyzer:

    @staticmethod
    def port_cargo_weight(ship: Ship) -> float:
        return sum(c.weight for c in ship.containers if c.side.lower() == "port")

    @staticmethod
    def starboard_cargo_weight(ship: Ship) -> float:
        return sum(c.weight for c in ship.containers if c.side.lower() == "starboard")

    @staticmethod
    def port_total_weight(ship: Ship) -> float:
        return StabilityAnalyzer.port_cargo_weight(ship) + ship.ballast_port()

    @staticmethod
    def starboard_total_weight(ship: Ship) -> float:
        return StabilityAnalyzer.starboard_cargo_weight(ship) + ship.ballast_starboard()

    @staticmethod
    def calculate_list(ship: Ship) -> float:
        """Positive = listing to starboard, negative = listing to port."""
        return (
            StabilityAnalyzer.starboard_total_weight(ship)
            - StabilityAnalyzer.port_total_weight(ship)
        )

    @staticmethod
    def calculate_trim(ship: Ship) -> float:
        """Positive = trimmed by stern, negative = trimmed by bow."""
        midpoint = ship.num_bays / 2

        fore_cargo = sum(c.weight for c in ship.containers if c.bay <= midpoint)
        aft_cargo  = sum(c.weight for c in ship.containers if c.bay >  midpoint)

        fore_ballast = sum(
            t.current_volume
            for k, t in ship.tanks.items()
            if int(k.split("_")[1]) <= midpoint
        )
        aft_ballast = sum(
            t.current_volume
            for k, t in ship.tanks.items()
            if int(k.split("_")[1]) > midpoint
        )

        return (aft_cargo + aft_ballast) - (fore_cargo + fore_ballast)

    @staticmethod
    def stability_score(ship: Ship) -> float:
        return (
            abs(StabilityAnalyzer.calculate_list(ship))
            + abs(StabilityAnalyzer.calculate_trim(ship))
        )

    @staticmethod
    def risk_level(ship: Ship) -> str:
        score = StabilityAnalyzer.stability_score(ship)
        if score < 100:
            return "SAFE"
        elif score < 250:
            return "WARNING"
        else:
            return "CRITICAL"


# -----------------------------
# Recommendation Engine
# -----------------------------
# Threshold aligned with risk_level: use 50 t as the action trigger
# (well inside the 100 t SAFE ceiling so advice fires before WARNING)
_ACTION_THRESHOLD = 50


class RecommendationEngine:

    @staticmethod
    def recommend(ship: Ship) -> List[str]:
        recommendations = []

        list_value = StabilityAnalyzer.calculate_list(ship)
        trim_value = StabilityAnalyzer.calculate_trim(ship)
        risk       = StabilityAnalyzer.risk_level(ship)

        # List (port-starboard imbalance)
        if list_value > _ACTION_THRESHOLD:
            diff = round(list_value)
            recommendations.append(
                f"Listing {diff} t to STARBOARD — transfer ballast to PORT tanks."
            )
        elif list_value < -_ACTION_THRESHOLD:
            diff = round(abs(list_value))
            recommendations.append(
                f"Listing {diff} t to PORT — transfer ballast to STARBOARD tanks."
            )

        # Trim (fore-aft imbalance)
        if trim_value > _ACTION_THRESHOLD:
            diff = round(trim_value)
            recommendations.append(
                f"Trimmed {diff} t by STERN — move ballast towards BOW."
            )
        elif trim_value < -_ACTION_THRESHOLD:
            diff = round(abs(trim_value))
            recommendations.append(
                f"Trimmed {diff} t by BOW — move ballast towards STERN."
            )

        # Risk-level escalation message
        if risk == "CRITICAL":
            recommendations.append(
                "⚠ CRITICAL stability risk — immediate corrective action required."
            )
        elif risk == "WARNING":
            recommendations.append(
                "⚠ WARNING — monitor closely and redistribute load."
            )

        if not recommendations:
            recommendations.append("Ship is stable. No action required.")

        return recommendations

    @staticmethod
    def best_position(ship: Ship, weight: float):
        """
        Find the (bay, side) that minimises combined list + trim after
        adding a container of the given weight.  Returns (bay, side, score).
        """
        best_bay   = None
        best_side  = None
        best_score = float("inf")

        # Snapshot current containers for thread-safety
        current_containers = list(ship.containers)

        for bay in range(1, ship.num_bays + 1):
            for side in ("port", "starboard"):

                # Skip occupied slots
                if any(c.bay == bay and c.side == side for c in current_containers):
                    continue

                # Evaluate candidate with virtual container without mutating ship.containers
                temp_containers = current_containers + [Container(id="__temp__", weight=weight, bay=bay, side=side)]
                p_cargo = sum(c.weight for c in temp_containers if c.side.lower() == "port")
                s_cargo = sum(c.weight for c in temp_containers if c.side.lower() == "starboard")
                p_total = p_cargo + ship.ballast_port()
                s_total = s_cargo + ship.ballast_starboard()
                list_val = s_total - p_total

                midpoint = ship.num_bays / 2
                fore_cargo = sum(c.weight for c in temp_containers if c.bay <= midpoint)
                aft_cargo  = sum(c.weight for c in temp_containers if c.bay > midpoint)
                fore_ballast = sum(t.current_volume for k, t in ship.tanks.items() if int(k.split("_")[1]) <= midpoint)
                aft_ballast = sum(t.current_volume for k, t in ship.tanks.items() if int(k.split("_")[1]) > midpoint)
                trim_val = (aft_cargo + aft_ballast) - (fore_cargo + fore_ballast)

                score = abs(list_val) + abs(trim_val)

                if score < best_score:
                    best_score = score
                    best_bay   = bay
                    best_side  = side

        return best_bay, best_side, best_score


# -----------------------------
# TEST DATA
# -----------------------------
if __name__ == "__main__":

    ship = Ship("MareTide Demo", num_bays=10)

    # Ballast tanks
    for i in range(1, 11):
        ship.tanks[f"port_{i}"]      = BallastTank(f"Port-{i}",      300, 300)
        ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)

    ship.add_container(Container(id="C001", weight=50,  bay=2, side="port"))
    ship.add_container(Container(id="C002", weight=300, bay=8, side="starboard"))

    # -----------------------------
    # OUTPUT
    # -----------------------------
    print("\n===== MareTide REPORT =====\n")

    print("Total Cargo   :", ship.total_cargo_weight(), "t")
    print("Port Cargo    :", StabilityAnalyzer.port_cargo_weight(ship), "t")
    print("Starboard Cargo:", StabilityAnalyzer.starboard_cargo_weight(ship), "t")
    print("List          :", StabilityAnalyzer.calculate_list(ship), "t")
    print("Trim          :", StabilityAnalyzer.calculate_trim(ship), "t")
    print("Risk          :", StabilityAnalyzer.risk_level(ship))

    print("\nRecommendations:")
    for rec in RecommendationEngine.recommend(ship):
        print(" -", rec)

    bay, side, score = RecommendationEngine.best_position(ship, 80)
    print(f"\nBest position for 80 t container → Bay {bay} | {side.upper()} (score {score:.1f})")

    DigitalTwin.display(ship, num_bays=ship.num_bays)
