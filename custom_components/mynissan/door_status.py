"""Conversions for reported openings and locks."""

from pynissan import VehicleStatus

from .timestamps import timestamp_attributes


def door_timestamp_attributes(status: VehicleStatus) -> dict[str, object]:
    """Return the observation time shared by reported openings and locks."""
    return timestamp_attributes(status.doors.last_updated_at if status.doors else None)


def opening_state(value: str | None) -> bool | None:
    """Return whether an opening is open without treating unknown as closed."""
    match value:
        case "OPEN":
            return True
        case "CLOSED":
            return False
        case _:
            return None


def window_state(value: str | None) -> bool | None:
    """Return whether a window is open, counting a partly open window as open."""
    match value:
        case "CLOSED":
            return False
        case str() if "OPEN" in value or value == "AJAR":
            return True
        case _:
            return None


def unlocked_state(value: str | None) -> bool | None:
    """Return whether a lock is unlocked without treating unknown as locked."""
    match value:
        case "UNLOCKED":
            return True
        case "LOCKED":
            return False
        case _:
            return None
