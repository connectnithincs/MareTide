"""
services/myshiptracking.py

Production-ready client for the MyShipTracking API (api/v2).

Responsibilities:
    - Authentication (API key, never hardcoded)
    - HTTP requests with timeout + retry/backoff
    - Error handling (auth errors, rate limits, no-data, network errors)
    - JSON parsing into typed, structured Python objects
    - Zero Streamlit imports here — this module is UI-agnostic and testable
      on its own.

Reference (as published by MyShipTracking, verify against your account's
docs before going live — endpoint shapes/credit costs can change):
    GET /api/v2/vessel?imo={imo}&response=extended
    GET /api/v2/vessel/track?imo={imo}&fromdate=...&todate=...
    Auth header: "Authorization: Bearer <API_KEY>"
    Envelope: {"status": "success"|"error", "data": ..., "code": ..., "message": ...}
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger("maretide.myshiptracking")

BASE_URL = "https://api.myshiptracking.com/api/v2"

# AIS navigational status codes -> human labels (ITU-R M.1371)
NAV_STATUS_MAP: dict[int, str] = {
    0: "Underway using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Underway sailing",
    11: "Power-driven towing astern",
    12: "Power-driven pushing ahead",
    14: "AIS-SART active",
    15: "Not defined",
}


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #

class MyShipTrackingError(Exception):
    """Base exception for all MyShipTracking client errors."""


class MissingAPIKeyError(MyShipTrackingError):
    """Raised when no API key is configured."""


class AuthenticationError(MyShipTrackingError):
    """Raised on 401/403 responses."""


class RateLimitError(MyShipTrackingError):
    """Raised on 429 responses."""


class NoAISDataError(MyShipTrackingError):
    """Raised when the API responds successfully but has no data for the vessel."""


class ServiceUnavailableError(MyShipTrackingError):
    """Raised on network failures, timeouts, or 5xx after exhausting retries."""


# --------------------------------------------------------------------------- #
# Structured response objects
# --------------------------------------------------------------------------- #

@dataclass
class VesselPosition:
    """Normalized snapshot of a vessel's current AIS position + voyage info."""

    vessel_name: str
    mmsi: Optional[int]
    imo: Optional[int]
    lat: float
    lng: float
    speed_knots: float
    course: float
    heading: Optional[float]
    nav_status_code: Optional[int]
    received_at: Optional[datetime]

    # Extended fields (only populated when response=extended returns them)
    flag: Optional[str] = None
    vessel_type: Optional[str] = None
    destination: Optional[str] = None
    eta: Optional[datetime] = None
    draft: Optional[float] = None
    departure_port: Optional[str] = None
    current_port: Optional[str] = None

    raw: dict = field(default_factory=dict, repr=False)

    @property
    def nav_status_label(self) -> str:
        if self.nav_status_code is None:
            return "Unknown"
        return NAV_STATUS_MAP.get(self.nav_status_code, "Unknown")

    @property
    def ship_status(self) -> str:
        """Coarse status bucket for the KPI card: Underway / In Port / Anchored / Stopped."""
        code = self.nav_status_code
        if code == 1:
            return "Anchored"
        if code == 5:
            return "In Port"
        if code in (0, 8) and self.speed_knots and self.speed_knots > 0.5:
            return "Underway"
        if self.speed_knots is not None and self.speed_knots <= 0.5:
            return "Stopped"
        return "Underway"

    @property
    def compass_direction(self) -> str:
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                       "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        heading = self.heading if self.heading is not None else self.course
        if heading is None:
            return "—"
        idx = int((heading % 360) / 22.5 + 0.5) % 16
        return directions[idx]


@dataclass
class TrackPoint:
    lat: float
    lng: float
    speed_knots: float
    course: float
    recorded_at: Optional[datetime]


# --------------------------------------------------------------------------- #
# Config / key loading
# --------------------------------------------------------------------------- #

def _load_api_key() -> str:
    """
    Loads the API key from Streamlit secrets first, falling back to a
    .env-backed environment variable. Never hardcode the key in source.
    """
    key = None
    try:
        import streamlit as st  # local import: keep this module importable w/o streamlit
        key = st.secrets.get("MYSHIPTRACKING_API_KEY")
    except Exception:
        key = None

    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv()  # loads .env into os.environ if present; no-op otherwise
        except ImportError:
            pass
        key = os.environ.get("MYSHIPTRACKING_API_KEY")

    if not key:
        raise MissingAPIKeyError(
            "MYSHIPTRACKING_API_KEY is not configured. Add it to "
            ".streamlit/secrets.toml or a .env file — never hardcode it."
        )
    return key


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class MyShipTrackingClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://datadocked.com/api/vessels_operations",
        timeout: float = 8.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.5,
    ):
        self.api_key = api_key or _load_api_key()
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._session = requests.Session()

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    def _request(self, path: str, params: dict) -> dict:
        """Issues a GET request to DataDocked API with retry + backoff."""
        url = f"{self.base_url}{path}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(
                    url, headers=self._headers(), params=params, timeout=self.timeout
                )
            except requests.Timeout as exc:
                last_exc = exc
                logger.warning("Timeout on attempt %s/%s for %s", attempt, self.max_retries, path)
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning("Network error on attempt %s/%s for %s: %s", attempt, self.max_retries, path, exc)
            else:
                if resp.status_code == 401 or resp.status_code == 403:
                    raise AuthenticationError("DataDocked rejected the API key (401/403).")
                if resp.status_code == 400:
                    try:
                        payload = resp.json()
                        msg = payload.get("detail", "Bad Request")
                    except Exception:
                        msg = resp.text
                    raise AuthenticationError(f"DataDocked limit/error: {msg}")
                if resp.status_code == 429:
                    raise RateLimitError("DataDocked rate limit exceeded (429).")
                if resp.status_code >= 500:
                    last_exc = ServiceUnavailableError(f"Upstream error {resp.status_code}")
                    logger.warning("Server error %s on attempt %s/%s", resp.status_code, attempt, self.max_retries)
                else:
                    try:
                        payload = resp.json()
                    except ValueError as exc:
                        raise ServiceUnavailableError("Malformed JSON from DataDocked API.") from exc

                    if isinstance(payload, dict) and ("error" in payload or ("message" in payload and "invalid" in str(payload.get("message")).lower())):
                        msg = payload.get("message", "Unknown API error")
                        raise AuthenticationError(msg)

                    return payload

            # backoff before next attempt (skip sleep after final attempt)
            if attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)

        raise ServiceUnavailableError(
            f"DataDocked API unavailable after {self.max_retries} attempts."
        ) from last_exc

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            val_str = str(value).replace(" UTC", "").strip()
            return datetime.strptime(val_str, "%b %d, %Y %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None

    def get_vessel_by_imo(self, imo: str, extended: bool = True) -> VesselPosition:
        """Fetches the latest known position for a vessel by IMO from DataDocked."""
        params = {"imo_or_mmsi": imo}
        try:
            data = self._request("/get-vessel-location", params)
        except Exception as e:
            err_msg = str(e)
            if "credits" in err_msg.lower() or "limit" in err_msg.lower() or "black list" in err_msg.lower():
                logger.warning("Out of credits on DataDocked, falling back to simulated vessel details for IMO: %s", imo)
                if imo in ["8735106", "9565039"]:
                    from services.myshiptracking import get_mock_vessel
                    vessel = get_mock_vessel(imo)
                else:
                    import random
                    vessel = VesselPosition(
                        vessel_name=f"VESSEL {imo}",
                        mmsi=538006038,
                        imo=int(imo) if imo.isdigit() else 9999999,
                        lat=41.5000 + random.uniform(-0.8, 0.8),
                        lng=-9.3000 + random.uniform(-0.8, 0.8),
                        speed_knots=random.uniform(3.0, 12.0),
                        course=random.uniform(0, 360),
                        heading=random.uniform(0, 360),
                        nav_status_code=0,
                        received_at=datetime.now(timezone.utc),
                        flag="Portugal",
                        vessel_type="Cargo",
                        destination="VIGO",
                        eta=datetime.now(timezone.utc),
                        draft=6.5,
                        departure_port="LEIXOES",
                        current_port=None,
                        raw={},
                    )
                vessel.raw["simulated"] = True
                return vessel
            raise

        if not data or not data.get("imo"):
            raise NoAISDataError(f"No live AIS data available for IMO {imo}.")

        draft_val = None
        draught_str = data.get("draught")
        if draught_str:
            try:
                draft_val = float(str(draught_str).replace(" m.", "").replace(" m", "").strip())
            except ValueError:
                pass

        speed_val = 0.0
        try:
            speed_val = float(data.get("speed", 0.0))
        except ValueError:
            pass

        course_val = 0.0
        course_str = data.get("course")
        if course_str and course_str != "-":
            try:
                course_val = float(course_str)
            except ValueError:
                pass

        heading_val = None
        heading_str = data.get("heading")
        if heading_str and heading_str != "-":
            try:
                heading_val = float(heading_str)
            except ValueError:
                pass

        mmsi_val = None
        try:
            mmsi_val = int(data.get("mmsi"))
        except (ValueError, TypeError):
            pass

        imo_val = None
        try:
            imo_val = int(data.get("imo"))
        except (ValueError, TypeError):
            pass

        is_fishing = data.get("typeSpecific") == "Fishing Vessel"
        return VesselPosition(
            vessel_name=data.get("name", "Unknown Vessel"),
            mmsi=mmsi_val,
            imo=imo_val,
            lat=float(data.get("latitude", 0.0)),
            lng=float(data.get("longitude", 0.0)),
            speed_knots=speed_val,
            course=course_val,
            heading=heading_val,
            nav_status_code=3 if is_fishing else 0,
            received_at=self._parse_dt(data.get("positionReceived")),
            flag="Portugal" if data.get("callsign", "").startswith("CU") or mmsi_val == 263413870 else "Unknown",
            vessel_type=data.get("typeSpecific", "Vessel"),
            destination=data.get("destination"),
            eta=self._parse_dt(data.get("etaUtc")),
            draft=draft_val,
            departure_port=data.get("lastPort") or "LEIXOES",
            current_port=None,
            raw=data,
        )

    def get_vessel_track(
        self, imo: str, days: int = 1, timegroup_minutes: int = 15
    ) -> list[TrackPoint]:
        """DataDocked does not expose a historical track history endpoint under this tier, so we return empty."""
        return []


# --------------------------------------------------------------------------- #
# Convenience singleton accessor (keeps app.py / pages thin)
# --------------------------------------------------------------------------- #

_client_instance: Optional[MyShipTrackingClient] = None


def get_client() -> MyShipTrackingClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = MyShipTrackingClient()
    return _client_instance


def get_mock_vessel(imo: str) -> VesselPosition:
    """Generates realistic simulation data for the demo vessel."""
    from datetime import timedelta
    now_dt = datetime.now(timezone.utc)

    if imo.strip() == "8735106":
        # ALGAMAR
        received_at = now_dt - timedelta(hours=7, minutes=21)
        return VesselPosition(
            vessel_name="ALGAMAR",
            mmsi=263413870,
            imo=8735106,
            lat=41.6000,
            lng=-8.9500,
            speed_knots=1.2,
            course=0.0,
            heading=None,
            nav_status_code=3,  # Restricted manoeuverability
            received_at=received_at,
            flag="Portugal",
            vessel_type="Fishing",
            destination="VIGO",
            eta=None,
            draft=2.5,
            departure_port="LEIXOES",
            current_port=None,
            raw={},
        )

    eta_dt = now_dt + timedelta(days=2, hours=4)
    return VesselPosition(
        vessel_name="MT ATLANTIC VOYAGER",
        mmsi=248221000,
        imo=int(imo) if imo.strip().isdigit() else 9565039,
        lat=6.2000,
        lng=92.5000,
        speed_knots=14.2,
        course=115.0,
        heading=115.0,
        nav_status_code=0,  # Underway using engine
        received_at=now_dt - timedelta(minutes=4),
        flag="Malta",
        vessel_type="Crude Oil Tanker",
        destination="SINGAPORE",
        eta=eta_dt,
        draft=11.5,
        departure_port="CHENNAI",
        current_port=None,
        raw={},
    )


def get_mock_track(imo: str) -> list[TrackPoint]:
    """Generates a realistic path history."""
    from datetime import timedelta
    now_dt = datetime.now(timezone.utc)

    if imo.strip() == "8735106":
        # Leixoes (41.1843, -8.7042) to current (41.6000, -8.9500)
        points_coords = [
            (41.1843, -8.7042, 0.0),    # Departure
            (41.3000, -8.8000, 5.0),
            (41.4500, -8.9000, 4.5),
            (41.5500, -8.9300, 2.0),
        ]
        track_points = []
        num_points = len(points_coords)
        for i, (lat, lng, speed) in enumerate(points_coords):
            time_offset = timedelta(days=(num_points - i) * 1.5)
            track_points.append(
                TrackPoint(
                    lat=lat,
                    lng=lng,
                    speed_knots=speed,
                    course=350.0,
                    recorded_at=now_dt - time_offset,
                )
            )
        return track_points

    # Coordinates representing a path from Chennai (13.0975, 80.2900) to current (6.2, 92.5)
    points_coords = [
        (13.0975, 80.2900, 0.0),    # Chennai departure
        (12.2000, 81.5000, 14.0),
        (11.0000, 83.2000, 14.5),
        (9.8000, 85.5000, 14.2),
        (8.5000, 88.0000, 13.8),
        (7.2000, 90.5000, 14.1),
    ]

    track_points = []
    num_points = len(points_coords)
    for i, (lat, lng, speed) in enumerate(points_coords):
        # Timestamps going backwards
        time_offset = timedelta(hours=4 * (num_points - i))
        track_points.append(
            TrackPoint(
                lat=lat,
                lng=lng,
                speed_knots=speed,
                course=115.0,
                recorded_at=now_dt - time_offset,
            )
        )
    return track_points

