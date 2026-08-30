"""
Phase 4D: Multi-Container Stowage Optimization Tests.
Verifies batch manifest sequence planning, copy-on-write stability progression,
fault isolation for invalid containers, VCG & hazardous ordering heuristics, and live-state immutability.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Container, StabilityAnalyzer
import state
from container_stability.models import (
    MultiContainerPlanRequest,
    MultiContainerExecuteRequest
)
from container_stability.analyzer import MultiContainerPlanner, ContainerStabilityService
from reports.logs_db import clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0
    yield
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0


# --- TEST 1: TWO CONTAINERS BALANCED PLACEMENT ---
def test_1_two_containers_balanced_placement():
    """Verify that a 2-container manifest produces balanced port & starboard placements."""
    req_payload = {
        "containers": [
            {
                "container_number": "MSCU1111001",
                "container_type": "40HC",
                "weights": {"gross_weight_kg": 20000.0},
                "cargo": {"hazardous": False}
            },
            {
                "container_number": "CMAU2222002",
                "container_type": "40HC",
                "weights": {"gross_weight_kg": 20000.0},
                "cargo": {"hazardous": False}
            }
        ]
    }

    res = client.post("/api/container/stability/manifest-plan", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["valid_count"] == 2
    assert data["rejected_count"] == 0
    assert len(data["loading_sequence"]) == 2
    assert len(data["stability_progression"]) == 3  # Initial + C1 + C2

    # Step 1 and Step 2 positions should alternate sides to maintain balance
    step1_side = data["loading_sequence"][0]["recommended_position"]["side"]
    step2_side = data["loading_sequence"][1]["recommended_position"]["side"]
    assert step1_side != step2_side, "Balanced pair should stow on opposite sides"

    # Final list should be 0.0 with identical weights on opposite sides
    assert data["final_stability"]["list_t"] == 0.0


# --- TEST 2: THREE CONTAINERS PROGRESSION ---
def test_2_three_containers_progression():
    """Verify stability progression across 3 containers."""
    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "CONT-A", "weights": {"gross_weight_kg": 22000.0}},
            {"container_number": "CONT-B", "weights": {"gross_weight_kg": 22000.0}},
            {"container_number": "CONT-C", "weights": {"gross_weight_kg": 15000.0}}
        ]
    )

    res = MultiContainerPlanner.plan_multi_container_stowage(req)
    assert res.success is True
    assert len(res.loading_sequence) == 3
    assert len(res.stability_progression) == 4  # Initial, C1, C2, C3

    assert res.stability_progression[0].label == "INITIAL"
    assert res.stability_progression[1].label == "AFTER_C1"
    assert res.stability_progression[2].label == "AFTER_C2"
    assert res.stability_progression[3].label == "AFTER_C3"


# --- TEST 3: CONFLICTING CONTAINERS RESOLUTION ---
def test_3_conflicting_containers_resolution():
    """Verify that multiple containers desiring the same optimal bay/side get distinct, sequentially valid slots."""
    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "CONF-1", "weights": {"gross_weight_kg": 25000.0}},
            {"container_number": "CONF-2", "weights": {"gross_weight_kg": 25000.0}},
            {"container_number": "CONF-3", "weights": {"gross_weight_kg": 25000.0}},
            {"container_number": "CONF-4", "weights": {"gross_weight_kg": 25000.0}}
        ]
    )

    res = MultiContainerPlanner.plan_multi_container_stowage(req)
    assert res.success is True
    assert res.valid_count == 4

    assigned_slots = [
        (s.recommended_position.bay, s.recommended_position.side, s.recommended_position.tier)
        for s in res.loading_sequence
    ]
    # All assigned slots must be unique
    assert len(assigned_slots) == len(set(assigned_slots)), "Assigned slots must not collide"


# --- TEST 4: INVALID CONTAINER FAULT ISOLATION ---
def test_4_invalid_container_fault_isolation():
    """Verify that an invalid container is isolated to rejected_containers without invalidating the valid manifest."""
    req_payload = {
        "containers": [
            {
                "container_number": "VALID-01",
                "weights": {"gross_weight_kg": 21000.0}
            },
            {
                "container_number": "INVALID-02",
                "weights": {"gross_weight_kg": 0.0}  # Invalid 0kg weight
            },
            {
                "container_number": "VALID-03",
                "weights": {"gross_weight_kg": 18000.0}
            }
        ]
    }

    res = client.post("/api/container/stability/manifest-plan", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["valid_count"] == 2
    assert data["rejected_count"] == 1
    assert data["rejected_containers"][0]["container_number"] == "INVALID-02"


# --- TEST 5: OCCUPIED SLOTS STACKING ADVANCEMENT ---
def test_5_occupied_slots_advancement():
    """Verify that prior occupied slots in vessel state correctly stack to next tier or alternative bays."""
    ship = state.get_current_ship()
    # Occupy Bay 2 Port Tier 1
    ship.containers.append(Container(id="PRE-OCC", weight=20.0, bay=2, side="port", tier=1))

    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "NEW-01", "weights": {"gross_weight_kg": 19000.0}}
        ]
    )

    res = MultiContainerPlanner.plan_multi_container_stowage(req, ship_instance=ship)
    assert res.success is True
    rec = res.loading_sequence[0].recommended_position
    # Slot assigned should not be Bay 2 Port Tier 1
    assert not (rec.bay == 2 and rec.side == "PORT" and rec.tier == 1)


# --- TEST 6: HEAVY CONTAINER VCG BASE TIER ORDERING ---
def test_6_heavy_container_vcg_base_tier_ordering():
    """Verify heavy containers are ordered first to secure low Tier 1 vertical center of gravity."""
    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "LIGHT-1", "weights": {"gross_weight_kg": 12000.0}},
            {"container_number": "HEAVY-1", "weights": {"gross_weight_kg": 30000.0}},
            {"container_number": "MEDIUM-1", "weights": {"gross_weight_kg": 20000.0}}
        ]
    )

    res = MultiContainerPlanner.plan_multi_container_stowage(req)
    assert res.success is True
    # In the optimized loading sequence, HEAVY-1 should be scheduled before LIGHT-1
    seq_ids = [s.container.container_number for s in res.loading_sequence]
    assert seq_ids[0] == "HEAVY-1", "Heaviest container must be sequenced first for deck base stability"


# --- TEST 7: HAZARDOUS CONTAINER OPEN DECK POSITIONING ---
def test_7_hazardous_container_deck_positioning():
    """Verify dangerous goods container is prioritized for open deck Tier 1."""
    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "STD-1", "weights": {"gross_weight_kg": 22000.0}, "cargo": {"hazardous": False}},
            {"container_number": "HAZ-1", "weights": {"gross_weight_kg": 18000.0}, "cargo": {"hazardous": True, "un_number": "UN 1993"}}
        ]
    )

    res = MultiContainerPlanner.plan_multi_container_stowage(req)
    assert res.success is True
    # HAZ-1 should be sequenced first and placed on Tier 1
    haz_step = next((s for s in res.loading_sequence if s.container.container_number == "HAZ-1"), None)
    assert haz_step is not None
    assert haz_step.step_number == 1
    assert haz_step.recommended_position.tier == 1


# --- TEST 8: NO VALID PLAN HANDLING ---
def test_8_no_valid_plan_handling():
    """Verify empty manifest or impossible plan returns success=False."""
    req = MultiContainerPlanRequest(containers=[])
    res = MultiContainerPlanner.plan_multi_container_stowage(req)
    assert res.success is False
    assert "No container entries supplied" in res.error_message


# --- TEST 9: DETERMINISTIC RESULTS ---
def test_9_deterministic_results():
    """Verify repeated evaluations on identical input produce strictly deterministic loading plans."""
    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "DET-A", "weights": {"gross_weight_kg": 24000.0}},
            {"container_number": "DET-B", "weights": {"gross_weight_kg": 19000.0}},
            {"container_number": "DET-C", "weights": {"gross_weight_kg": 27000.0}}
        ]
    )

    res1 = MultiContainerPlanner.plan_multi_container_stowage(req)
    res2 = MultiContainerPlanner.plan_multi_container_stowage(req)

    seq1 = [(s.container.container_number, s.recommended_position.bay, s.recommended_position.side) for s in res1.loading_sequence]
    seq2 = [(s.container.container_number, s.recommended_position.bay, s.recommended_position.side) for s in res2.loading_sequence]
    assert seq1 == seq2


# --- TEST 10: LIVE STATE COPY-ON-WRITE IMMUTABILITY & EXECUTION ---
def test_10_live_state_immutability_and_execution():
    """Verify planning does not mutate live vessel, and execution requires operator authorization."""
    ship = state.get_current_ship()
    initial_count = len(ship.containers)

    req = MultiContainerPlanRequest(
        containers=[
            {"container_number": "EXEC-1", "weights": {"gross_weight_kg": 22000.0}},
            {"container_number": "EXEC-2", "weights": {"gross_weight_kg": 22000.0}}
        ]
    )

    plan = MultiContainerPlanner.plan_multi_container_stowage(req)
    assert plan.success is True

    # 1. Assert live state remains untouched after planning
    assert len(ship.containers) == initial_count

    # 2. Assert unconfirmed execution is rejected
    unconfirmed_req = MultiContainerExecuteRequest(
        loading_sequence=[s.model_dump() for s in plan.loading_sequence],
        operator_confirmed=False
    )
    exec_res_unconf = MultiContainerPlanner.execute_multi_container_plan(unconfirmed_req)
    assert exec_res_unconf.success is False
    assert exec_res_unconf.status == "rejected"
    assert len(ship.containers) == initial_count

    # 3. Assert confirmed execution adds containers to live state
    confirmed_req = MultiContainerExecuteRequest(
        loading_sequence=[s.model_dump() for s in plan.loading_sequence],
        operator_confirmed=True
    )
    exec_res_conf = MultiContainerPlanner.execute_multi_container_plan(confirmed_req)
    assert exec_res_conf.success is True
    assert exec_res_conf.status == "COMPLETED"
    assert len(ship.containers) == initial_count + 2


# --- TEST 11: SINGLE-CONTAINER REGRESSION COMPATIBILITY ---
def test_11_single_container_regression_compatibility():
    """Verify single-container endpoint /api/container/stability/analyze continues to operate flawlessly."""
    req_payload = {
        "container": {
            "container_number": "SINGLE001",
            "weights": {"gross_weight_kg": 23500.0}
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True}
    }

    res = client.post("/api/container/stability/analyze", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["recommendation"]["bay"] is not None
    assert "structured_explanations" in data
    assert "provenance" in data
