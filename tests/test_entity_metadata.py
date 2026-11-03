"""Check entity translations and packaged metadata."""

import json
from pathlib import Path

import pytest

from custom_components.mynissan.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    DOOR_SENSOR_DESCRIPTIONS,
    WINDOW_SENSOR_DESCRIPTIONS,
)
from custom_components.mynissan.button import BUTTON_DESCRIPTIONS
from custom_components.mynissan.charge_completion import NissanChargeCompletionSensor
from custom_components.mynissan.engine_history import ENGINE_HISTORY_DESCRIPTIONS
from custom_components.mynissan.image import NissanVehicleImage
from custom_components.mynissan.lock import NissanDoorLock
from custom_components.mynissan.number import TEMPERATURE_DESCRIPTION
from custom_components.mynissan.refresh import NissanRefreshButton
from custom_components.mynissan.select import SEAT_DESCRIPTIONS
from custom_components.mynissan.sensor import (
    BATTERY_SENSOR_DESCRIPTIONS,
    CLIMATE_SENSOR_DESCRIPTIONS,
    FUEL_RANGE_DESCRIPTION,
    ODOMETER_DESCRIPTION,
    OIL_CHANGE_RANGE_DESCRIPTION,
    TIRE_SENSOR_DESCRIPTIONS,
    WARNINGS_DESCRIPTION,
)
from custom_components.mynissan.switch import SWITCH_DESCRIPTIONS


@pytest.mark.parametrize(
    "language",
    sorted(
        path.stem
        for path in (
            Path(__file__).resolve().parents[1] / "custom_components/mynissan/translations"
        ).glob("*.json")
    ),
)
def test_entity_translations(language: str) -> None:
    """Every added entity and command error has a translated label."""
    path = Path(__file__).resolve().parents[1] / "custom_components" / "mynissan" / "translations"
    document = json.loads((path / f"{language}.json").read_text(encoding="utf-8"))
    for platform, descriptions in (
        (
            "sensor",
            (
                *BATTERY_SENSOR_DESCRIPTIONS,
                *CLIMATE_SENSOR_DESCRIPTIONS,
                *TIRE_SENSOR_DESCRIPTIONS,
                ODOMETER_DESCRIPTION,
                FUEL_RANGE_DESCRIPTION,
                OIL_CHANGE_RANGE_DESCRIPTION,
                WARNINGS_DESCRIPTION,
                NissanChargeCompletionSensor.entity_description,
                *ENGINE_HISTORY_DESCRIPTIONS.values(),
            ),
        ),
        (
            "binary_sensor",
            (*BINARY_SENSOR_DESCRIPTIONS, *DOOR_SENSOR_DESCRIPTIONS, *WINDOW_SENSOR_DESCRIPTIONS),
        ),
        ("button", (*BUTTON_DESCRIPTIONS, NissanRefreshButton.entity_description)),
        ("lock", (NissanDoorLock.entity_description,)),
        ("image", (NissanVehicleImage.entity_description,)),
        ("number", (TEMPERATURE_DESCRIPTION,)),
        ("select", tuple(SEAT_DESCRIPTIONS.values())),
        ("switch", SWITCH_DESCRIPTIONS),
    ):
        for description in descriptions:
            assert document["entity"][platform][description.translation_key]["name"].strip()
    for key in (
        "command_failed",
        "command_rejected",
        "command_not_supported",
        "engine_command_rejected",
        "not_remote_engine_start",
        "invalid_remote_start_option",
    ):
        assert document["exceptions"][key]["message"].strip()
