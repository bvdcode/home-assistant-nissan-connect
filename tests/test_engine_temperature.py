"""Tests for restoring remote engine temperature across unit-system changes."""

from dataclasses import replace

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pynissan import HvacTemperatureCapabilities, TemperatureUnit
from pytest_homeassistant.common import mock_restore_cache_with_extra_data

from .test_engine_climate import ACCESSORIES, _start, setup_engine


@pytest.mark.parametrize(
    ("previous_unit", "previous_value", "current_unit", "expected"),
    [
        ("°C", 25.0, TemperatureUnit.FAHRENHEIT, 77.0),
        ("°F", 77.0, TemperatureUnit.CELSIUS, 25.0),
        ("°F", 95.0, TemperatureUnit.CELSIUS, 22.0),
    ],
)
async def test_restored_temperature_uses_its_stored_unit(
    hass: HomeAssistant,
    previous_unit: str,
    previous_value: float,
    current_unit: TemperatureUnit,
    expected: float,
) -> None:
    """Unit changes preserve the requested temperature while respecting the new range."""
    match current_unit:
        case TemperatureUnit.CELSIUS:
            units = METRIC_SYSTEM
            temperatures = HvacTemperatureCapabilities(
                unit=current_unit.value, default=22.0, minimum=16.0, maximum=30.0, resolution=0.5
            )
        case TemperatureUnit.FAHRENHEIT:
            units = US_CUSTOMARY_SYSTEM
            assert ACCESSORIES.hvac_temperatures is not None
            temperatures = ACCESSORIES.hvac_temperatures
        case _:
            pytest.fail(f"Unexpected temperature unit: {current_unit}")
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("number.family_ariya_remote_start_temperature", str(previous_value)),
                {
                    "native_max_value": None,
                    "native_min_value": None,
                    "native_step": None,
                    "native_unit_of_measurement": previous_unit,
                    "native_value": previous_value,
                },
            ),
        ),
    )
    client = await setup_engine(
        hass,
        defaults=None,
        accessories=replace(ACCESSORIES, hvac_temperatures=temperatures),
        units=units,
    )
    await _start(hass)
    requested = client.async_start_engine.await_args.kwargs["climate"]
    assert requested.temperature == pytest.approx(expected)
    assert requested.unit is current_unit
