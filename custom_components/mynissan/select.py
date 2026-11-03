"""Seat heating and cooling requested with each remote engine start."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import SeatClimateOption, Vehicle

from .coordinator import NissanDataUpdateCoordinator
from .engine_climate import SEAT_POSITIONS, EngineClimate
from .engine_settings import NissanEngineSetting
from .models import NissanConfigEntry

SEAT_DESCRIPTIONS: dict[str, SelectEntityDescription] = {
    position: SelectEntityDescription(
        key=f"remote_start_{position}_seat",
        translation_key=f"remote_start_{position}_seat",
        icon="mdi:car-seat-heater",
    )
    for _, position in SEAT_POSITIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose one seat mode per seat that supports remote heating or cooling."""
    del hass
    runtime = entry.runtime_data
    async_add_entities(
        NissanEngineSeat(runtime.coordinator, vehicle, climate, position)
        for vehicle in runtime.vehicles
        if (climate := runtime.engine_climate.get(vehicle.vin)) is not None
        for position in climate.seat_options
    )


class NissanEngineSeat(NissanEngineSetting, SelectEntity):
    """Heat, cool or leave off one seat on the next remote engine start."""

    entity_description: SelectEntityDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        climate: EngineClimate,
        position: str,
    ) -> None:
        """Initialize the seat setting with the modes this seat supports."""
        self.entity_description = SEAT_DESCRIPTIONS[position]
        super().__init__(coordinator, vehicle, climate)
        self._position = position
        self._attr_options = [option.value.lower() for option in climate.seat_options[position]]

    async def async_added_to_hass(self) -> None:
        """Keep the seat mode chosen before Home Assistant restarted."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self.options:
            self._climate.seats[self._position] = SeatClimateOption(last.state.upper())

    @property
    def current_option(self) -> str:
        """Return the seat mode sent with the next start."""
        return self._climate.seats[self._position].value.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the seat mode sent with the next start."""
        self._climate.seats[self._position] = SeatClimateOption(option.upper())
        self.async_write_ha_state()
