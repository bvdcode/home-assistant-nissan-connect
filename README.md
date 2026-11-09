# MyNISSAN for Home Assistant

[![CI](https://github.com/bvdcode/home-assistant-nissan-connect/actions/workflows/ci.yml/badge.svg)](https://github.com/bvdcode/home-assistant-nissan-connect/actions/workflows/ci.yml)
[![HACS](https://github.com/bvdcode/home-assistant-nissan-connect/actions/workflows/hacs.yml/badge.svg)](https://github.com/bvdcode/home-assistant-nissan-connect/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/bvdcode/home-assistant-nissan-connect/actions/workflows/hassfest.yml/badge.svg)](https://github.com/bvdcode/home-assistant-nissan-connect/actions/workflows/hassfest.yml)
[![Support on Ko-fi](https://img.shields.io/badge/Support_on_Ko--fi-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/bvdcode)

[![Open your Home Assistant instance and open this repository in the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bvdcode&repository=home-assistant-nissan-connect&category=integration)
[![Open your Home Assistant instance and start setting up the MyNISSAN integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mynissan)

MyNISSAN connects supported Nissan vehicles to Home Assistant through the
MyNISSAN cloud service.

The integration provides:

- configuration through the Home Assistant user interface;
- account authentication and automatic token refresh;
- discovery of every vehicle attached to the account;
- one Home Assistant device per vehicle;
- battery level, charging, plugged-in state, range, and climate sensors;
- remaining charging time and estimated completion time;
- odometer and individual tire pressures with reported status codes;
- door, hood, trunk, and lock status;
- vehicle-reported timestamps in the `last_updated_at` attribute of odometer,
  tire-pressure, door, and lock entities, when available;
- active warning count with messages in the sensor attributes;
- vehicle artwork as an image entity and map picture, with the paint code;
- last reported vehicle location on the Home Assistant map;
- a Refresh button to request fresh vehicle, battery, and climate status on demand;
- remote climate start, stop, and target-temperature control;
- remote engine start and stop for vehicles with the remote engine service, with
  cabin temperature, seat heating or cooling, steering wheel heat, and defrost
  settings for each start, and the time of the last start and stop sent from
  Home Assistant;
- door locking/unlocking and buttons for flashing lights or flashing lights with the horn;
- setup, entity names, and errors translated into 13 languages.

Available entities depend on the data reported for each vehicle. Remote controls
require an enabled service and an active subscription. Lock and light/horn commands
recheck these conditions before sending a request and wait for the reported result.
A vehicle with only locking or only unlocking support gets a button for that action
instead of a two-way lock control.

Remote engine start sends the temperature, seat, steering wheel, and defrost
settings shown on the vehicle's configuration controls. They start from the defaults
saved in the MyNISSAN app and only list the seats and options the vehicle reports.
The `mynissan.remote_engine_start` action starts the engine with different settings
for one start, for example based on the outside temperature:

```yaml
action: mynissan.remote_engine_start
target:
  entity_id: button.pathfinder_remote_engine_start
data:
  temperature: 72
  front_seats: heat
  steering_wheel_heater: true
  defrost: true
```

Vehicles do not report whether the engine is running, so Last remote engine start
and Last remote engine stop only record successful commands sent from Home
Assistant. Nissan refuses a start when the vehicle is not ready, for example after
two remote starts without driving in between, with a door unlocked or open, the
hood, the trunk or a window open, or a key inside; the error lists these causes.

Refresh requests fresh vehicle status and waits for the request to complete, then
refreshes battery and climate data when reported by the vehicle and reloads the
cloud readings. This happens only when the button is pressed. It can wake the
vehicle and use its 12 V battery; scheduled updates only read cached cloud data.

Charging time is reported in minutes, including while unplugged when supplied by
the vehicle. Estimated completion is available only while charging and calculated
from the remaining duration at the time the cached status is fetched; it is not a
completion time reported by the vehicle. The estimate is cleared when charging
stops or the remaining duration is unknown. Vehicle status is refreshed every 15 minutes, so it
can lag behind the vehicle. Home Assistant converts distance and pressure readings
to the configured units. Unknown door and lock values are not treated as closed or
locked. The vehicle image is model artwork supplied by the account, not a live camera.

## Requirements

- Home Assistant 2026.11.0 or newer;
- a MyNISSAN account from the United States or Canada, or a MiNissan account
  from Mexico, with at least one connected vehicle.

## Installation

The integration is available in HACS.

1. Open HACS.
2. Search for **MyNISSAN**.
3. Install **MyNISSAN** and restart Home Assistant.

## Configuration

1. Open **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **MyNISSAN**.
4. Select the account country and enter the email address and password used by
   the MyNISSAN or MiNissan app.

The password is used only while authenticating and is not stored. Home Assistant
stores the issued OAuth tokens and device identifier in the config entry so the
integration can reconnect and refresh its session.

## Development

The integration uses [`pynissan`](https://pypi.org/project/pynissan/) for all
communication with MyNISSAN services.

```bash
python -m pip install -r requirements_test.txt
ruff check .
ruff format --check .
mypy custom_components/mynissan tests
pytest
```

## Project status

This is a community-maintained project and is not affiliated with, endorsed by,
or associated with Nissan Motor Co., Ltd. Nissan and MyNISSAN are trademarks of
their respective owners.
