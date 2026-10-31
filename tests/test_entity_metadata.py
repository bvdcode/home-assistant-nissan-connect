"""Check entity translations and packaged metadata."""

import json
from pathlib import Path

import pytest

from custom_components.mynissan.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    DOOR_SENSOR_DESCRIPTIONS,
)
from custom_components.mynissan.button import BUTTON_DESCRIPTIONS
from custom_components.mynissan.charge_completion import NissanChargeCompletionSensor
from custom_components.mynissan.image import NissanVehicleImage
from custom_components.mynissan.lock import NissanDoorLock
from custom_components.mynissan.sensor import (
    BATTERY_SENSOR_DESCRIPTIONS,
    CLIMATE_SENSOR_DESCRIPTIONS,
    ODOMETER_DESCRIPTION,
    TIRE_SENSOR_DESCRIPTIONS,
    WARNINGS_DESCRIPTION,
)


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
                WARNINGS_DESCRIPTION,
                NissanChargeCompletionSensor.entity_description,
            ),
        ),
        ("binary_sensor", (*BINARY_SENSOR_DESCRIPTIONS, *DOOR_SENSOR_DESCRIPTIONS)),
        ("button", BUTTON_DESCRIPTIONS),
        ("lock", (NissanDoorLock.entity_description,)),
        ("image", (NissanVehicleImage.entity_description,)),
    ):
        for description in descriptions:
            assert document["entity"][platform][description.translation_key]["name"].strip()
    for key in ("command_failed", "command_rejected", "command_not_supported"):
        assert document["exceptions"][key]["message"].strip()
