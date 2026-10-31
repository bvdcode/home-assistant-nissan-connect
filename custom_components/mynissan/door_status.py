"""Conversions for reported openings and locks."""


def opening_state(value: str | None) -> bool | None:
    """Return whether an opening is open without treating unknown as closed."""
    match value:
        case "OPEN":
            return True
        case "CLOSED":
            return False
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
