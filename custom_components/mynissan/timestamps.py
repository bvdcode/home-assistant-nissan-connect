"""State attributes for observation times reported by the vehicle."""

from datetime import datetime


def timestamp_attributes(value: datetime | None) -> dict[str, object]:
    """Expose the reported time in ISO 8601 format when it is available."""
    if value is None:
        return {}
    return {"last_updated_at": value.isoformat()}
