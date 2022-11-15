"""
A integration that allows you to get information about next departure from specified stop.
For more details about this component, please refer to the documentation at
https://github.com/tofuSCHNITZEL/home-assistant-wienerlinien
"""
from datetime import datetime, timedelta, time
import json
import logging

import async_timeout
from requests.models import PreparedRequest
import voluptuous as vol

from config.custom_components.oebb.const import BASE_URL
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.light import LightEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

CONF_L = "L"
CONF_EVAID = "evaId"
CONF_BOARDTYPE = "boardType"
CONF_PRODUCTSFILTER = "productsFilter"
CONF_DIRINPUT = "dirInput"
CONF_TICKERID = "tickerID"
CONF_START = "start"
CONF_EQSTOPS = "eqstops"
CONF_SHOWJOURNEYS = "showJourneys"
CONF_ADDITIONALTIME = "additionaTime"

# https://fahrplan.oebb.at/bin/stboard.exe/dn?L=vs_liveticker&evaId=491116&boardType=dep&productsFilter=1011111111011&dirInput=491123&tickerID=dep&start=yes&eqstops=false&showJourneys=12&additionalTime=0&outputMode=tickerDataOnly


SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_L, default="vs_liveticker"): cv.string,
        vol.Required(CONF_EVAID, default=None): cv.Number,
        vol.Optional(CONF_BOARDTYPE, default="dep"): cv.string,
        vol.Optional(CONF_PRODUCTSFILTER, default=1011111111011): cv.Number,
        vol.Optional(CONF_DIRINPUT, default=""): cv.Number,
        vol.Optional(CONF_TICKERID, default="dep"): cv.string,
        vol.Optional(CONF_START, default="yes"): cv.string,
        vol.Optional(CONF_EQSTOPS, default="false"): cv.string,
        vol.Optional(CONF_SHOWJOURNEYS, default=12): cv.Number,
        vol.Optional(CONF_ADDITIONALTIME, default=0): cv.Number,
    }
)


_LOGGER = logging.getLogger(__name__)


class OebbAPI:
    """Call API."""

    def __init__(self, session, loop, params):
        """Initialize."""
        self.params = params
        self.loop = loop
        self.session = session
        self._name = "oebb_api"
        self._state = None
        self.data = {}
        self.attributes = {}

        req = PreparedRequest()
        req.prepare_url(BASE_URL, self.params)
        self.url = req.url
        self._attr_unique_id = self.url

    async def fetch_data(self):
        """Get json from API endpoint."""
        value = None

        _LOGGER.debug("Inside get JSON")

        try:
            async with async_timeout.timeout(10):

                response = await self.session.get(self.url)

        except Exception:
            pass
        string = str(response.content._buffer[0]).replace("\\n", "")[16:-1]

        value = json.loads(string)

        return value


class OebbCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, oebb_api: OebbAPI):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="My sensor",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.oebb_api = oebb_api

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await self.oebb_api.fetch_data()

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class OebbSensor(CoordinatorEntity, LightEntity):
    """OebbSensor."""

    def __init__(self, coordinator: OebbCoordinator, idx, evaId):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx
        self.formatted_idx = f"{self.idx:02}"
        self._name = "oebb_journey_" + str(idx)
        self._state = None
        self.attributes = {}

        self._attr_unique_id = str(evaId) + "_" + str(idx)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data

        self.attributes = {
            "startTime": data["journey"][self.idx]["ti"],
            "lastStop": data["journey"][self.idx]["lastStop"],
            "line": data["journey"][self.idx]["pr"],
            #    "provider": "oebb",
        }

        # self._name = self.attributes["startTime"]

        now = datetime.now()
        date_string = now.strftime("%d/%m/%Y")
        timestamp_string = date_string + " " + self.attributes["startTime"]

        self._state = datetime.strptime(timestamp_string, "%d/%m/%Y %H:%M")

        self.async_write_ha_state()

    # async def async_turn_on(self, **kwargs):
    #     """Turn the light on.

    #     Example method how to request data updates.
    #     """
    #     # Do the turning on.
    #     # ...

    #     # Update the data
    #     await self.coordinator.async_request_refresh()

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def state(self):
        """Return state."""
        return self._state

    @property
    def icon(self):
        """Return icon."""
        return "mdi:bus"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self.attributes

    @property
    def device_class(self):
        """Return device_class."""
        return "timestamp"


async def async_setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup."""

    params = {
        "L": config.get(CONF_L),
        "evaId": config.get(CONF_EVAID),
        "boardType": config.get(CONF_BOARDTYPE),
        "productsFilter": config.get(CONF_PRODUCTSFILTER),
        "dirInput": config.get(CONF_DIRINPUT),
        "tickerID": config.get(CONF_TICKERID),
        "start": config.get(CONF_START),
        "eqstops": config.get(CONF_EQSTOPS),
        "showJourneys": config.get(CONF_SHOWJOURNEYS),
        "additionalTime": config.get(CONF_ADDITIONALTIME),
        "outputMode": "tickerDataOnly",
    }

    # devices = []
    # api is my coordinator
    api = OebbAPI(async_create_clientsession(hass), hass.loop, params)
    coordinator = OebbCoordinator(hass, api)
    # data = await api.get_json()
    # _LOGGER.debug(len(data["journey"]))

    await coordinator.async_config_entry_first_refresh()

    devices = []

    for idx, entity in enumerate(coordinator.data):
        devices.append(OebbSensor(coordinator, idx, params["evaId"]))
    add_devices_callback(devices, True)
