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
- remote climate start, stop, and target-temperature control;
- door locking/unlocking and buttons for flashing lights or flashing lights with the horn;
- setup, entity names, and errors translated into 13 languages.

Available entities depend on the data reported for each vehicle. Remote controls
require an enabled service and an active subscription. Lock and light/horn commands
recheck these conditions before sending a request and wait for the reported result.
A vehicle with only locking or only unlocking support gets a button for that action
instead of a two-way lock control.

Charging time is reported in minutes, including while unplugged when supplied by
the vehicle. Estimated completion is available only while charging and calculated
from the remaining duration at the time the cached status is fetched; it is not a
completion time reported by the vehicle. The estimate is cleared when charging
stops or the remaining duration is unknown. Vehicle status is refreshed every 15 minutes, so it
can lag behind the vehicle. Home Assistant converts distance and pressure readings
to the configured units. Unknown door and lock values are not treated as closed or
locked. The vehicle image is model artwork supplied by the account, not a live camera.

## Requirements

- Home Assistant 2026.7.4 or newer;
- a MyNISSAN account from the United States or Canada, or a MiNissan account
  from Mexico, with at least one connected vehicle.

## Installation

The integration is available through HACS as a custom repository while its
default-catalog submission is under review.

1. Open HACS.
2. Select **Integrations**.
3. Open the menu and select **Custom repositories**.
4. Add `https://github.com/bvdcode/home-assistant-nissan-connect` as an
   **Integration** repository.
5. Install **MyNISSAN** and restart Home Assistant.

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
