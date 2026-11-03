"""Tests for resolving remote engine start action targets."""

import pytest
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockUser

from custom_components.mynissan.const import DOMAIN

from .test_engine_climate import _entity_id, setup_engine


@pytest.mark.parametrize("target_type", ["device_id", "area_id", "entity_id"])
async def test_vehicle_targets_start_only_the_engine(hass: HomeAssistant, target_type: str) -> None:
    """Device, area and all-entity targets ignore other vehicle buttons."""
    client = await setup_engine(hass)
    entry = er.async_get(hass).async_get(_entity_id(hass, Platform.BUTTON, "remote_engine_start"))
    assert entry is not None
    assert entry.device_id is not None
    match target_type:
        case "device_id":
            target_value = entry.device_id
        case "area_id":
            area = ar.async_get(hass).async_create("Garage")
            dr.async_get(hass).async_update_device(entry.device_id, area_id=area.id)
            target_value = area.id
        case "entity_id":
            target_value = "all"
        case _:
            pytest.fail(f"Unexpected target type: {target_type}")
    await hass.services.async_call(
        DOMAIN, "remote_engine_start", {target_type: target_value}, blocking=True
    )
    client.async_start_engine.assert_awaited_once()
    client.async_get_vehicle_status.assert_awaited_once()


async def test_invalid_explicit_target_prevents_every_start(hass: HomeAssistant) -> None:
    """A mixed valid and invalid explicit target list is rejected before dispatch."""
    client = await setup_engine(hass)
    refresh = _entity_id(hass, Platform.BUTTON, "refresh")
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            "remote_engine_start",
            {
                "entity_id": [
                    _entity_id(hass, Platform.BUTTON, "remote_engine_start"),
                    refresh,
                ]
            },
            blocking=True,
        )
    assert error.value.translation_key == "not_remote_engine_start"
    assert error.value.translation_placeholders == {"entity_id": refresh}
    client.async_start_engine.assert_not_called()


async def test_vehicle_target_keeps_entity_permission_checks(hass: HomeAssistant) -> None:
    """Targeting a vehicle does not bypass the engine entity's access permissions."""
    client = await setup_engine(hass)
    entry = er.async_get(hass).async_get(_entity_id(hass, Platform.BUTTON, "remote_engine_start"))
    assert entry is not None
    user = MockUser().add_to_hass(hass)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "remote_engine_start",
            {"device_id": entry.device_id},
            blocking=True,
            context=Context(user_id=user.id),
        )
    client.async_start_engine.assert_not_called()
