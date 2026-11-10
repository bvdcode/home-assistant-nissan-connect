"""Cabin climate settings sent with each remote engine start."""

from dataclasses import dataclass, field

from pynissan import (
    ClimateDefaults,
    ClimateParameters,
    ClimateSettings,
    SeatClimateOption,
    SeatClimateSettings,
    TemperatureUnit,
    VehicleCapabilities,
)

# Capability field reported by the vehicle and the matching SDK seat field.
SEAT_POSITIONS: tuple[tuple[str, str], ...] = (
    ("driver_seat", "front_driver"),
    ("assistant_seat", "front_passenger"),
    ("second_left_seat", "rear_left"),
    ("second_right_seat", "rear_right"),
    ("second_centre_seat", "rear_center"),
    ("third_left_seat", "third_left"),
    ("third_right_seat", "third_right"),
)
SEAT_SUPPORT: dict[str, tuple[SeatClimateOption, ...]] = {
    "HEATING": (SeatClimateOption.OFF, SeatClimateOption.HEAT),
    "COOLING": (SeatClimateOption.OFF, SeatClimateOption.COOL),
    "HEATING_AND_COOLING": (
        SeatClimateOption.OFF,
        SeatClimateOption.HEAT,
        SeatClimateOption.COOL,
    ),
}
# Service the MyNISSAN app requires before it sends climate settings with a start.
HVAC_ACCESSORIES_SERVICE = "HVAC_ACCESSORIES"


def supports_engine_climate(capabilities: VehicleCapabilities) -> bool:
    """Whether the vehicle accepts climate settings with a remote engine start.

    Vehicles without an enabled HVAC accessories service refuse a start that
    carries climate settings, so the MyNISSAN app sends them a plain start.
    """
    return any(
        service.type == HVAC_ACCESSORIES_SERVICE and service.enabled
        for service in capabilities.services
    )


@dataclass(slots=True)
class EngineClimate:
    """Editable climate request for one vehicle's remote engine starts."""

    unit: TemperatureUnit
    temperature: float
    minimum: float
    maximum: float
    step: float
    seat_options: dict[str, tuple[SeatClimateOption, ...]]
    seats: dict[str, SeatClimateOption] = field(default_factory=dict)
    steering_wheel_heater: bool | None = None
    defrost: bool = False

    def settings(
        self,
        *,
        temperature: float | None = None,
        seats: dict[str, SeatClimateOption] | None = None,
        steering_wheel_heater: bool | None = None,
        defrost: bool | None = None,
    ) -> ClimateSettings:
        """Build the start request, optionally overriding individual settings."""
        seat_modes = {**self.seats, **(seats or {})}
        wheel = self.steering_wheel_heater
        if wheel is not None and steering_wheel_heater is not None:
            wheel = steering_wheel_heater
        return ClimateSettings(
            temperature=self.temperature if temperature is None else temperature,
            unit=self.unit,
            parameters=ClimateParameters(
                seats=SeatClimateSettings(**seat_modes) if self.seat_options else None,
                steering_wheel_heater=wheel,
                defrost_and_deicer=self.defrost if defrost is None else defrost,
            ),
        )


def engine_climate(
    capabilities: VehicleCapabilities,
    defaults: ClimateDefaults | None,
) -> EngineClimate | None:
    """Describe the climate options a vehicle accepts with a remote engine start."""
    if not supports_engine_climate(capabilities):
        return None
    details = capabilities.accessories_details
    if details is None or details.hvac_temperatures is None:
        return None
    temperatures = details.hvac_temperatures
    try:
        unit = TemperatureUnit(temperatures.unit)
    except ValueError:
        return None
    if unit is TemperatureUnit.UNKNOWN_VALUE:
        return None
    seat_options: dict[str, tuple[SeatClimateOption, ...]] = {}
    seat_heater = details.seat_heater
    if seat_heater is not None and seat_heater.enabled and seat_heater.accessories is not None:
        for capability_field, position in SEAT_POSITIONS:
            support = getattr(seat_heater.accessories, capability_field)
            if support in SEAT_SUPPORT:
                seat_options[position] = SEAT_SUPPORT[support]
    wheel_supported = details.steering_heat is not None and details.steering_heat.enabled is True
    climate = EngineClimate(
        unit=unit,
        temperature=temperatures.default,
        minimum=temperatures.minimum,
        maximum=temperatures.maximum,
        step=temperatures.resolution,
        seat_options=seat_options,
        seats=dict.fromkeys(seat_options, SeatClimateOption.OFF),
        steering_wheel_heater=False if wheel_supported else None,
    )
    if defaults is not None:
        _apply_defaults(climate, defaults)
    return climate


def _apply_defaults(climate: EngineClimate, defaults: ClimateDefaults) -> None:
    """Start from the settings saved in the MyNISSAN app."""
    saved = defaults.climate
    if (
        saved is not None
        and saved.unit == climate.unit
        and climate.minimum <= saved.value <= climate.maximum
    ):
        climate.temperature = saved.value
    parameters = defaults.parameters
    if parameters is None:
        return
    if parameters.seats is not None:
        for position, options in climate.seat_options.items():
            mode = getattr(parameters.seats, position)
            if mode in options:
                climate.seats[position] = mode
    if climate.steering_wheel_heater is not None and parameters.steering_wheel_heater is not None:
        climate.steering_wheel_heater = parameters.steering_wheel_heater
    if parameters.defrost_and_deicer is not None:
        climate.defrost = parameters.defrost_and_deicer
