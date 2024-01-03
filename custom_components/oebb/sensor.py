"""
A integration that allows you to get information about next departure from specified stop.
For more details about this component, please refer to the documentation at
https://github.com/lollopod/home-assistant-oebb
"""
from datetime import datetime, timedelta
import json
import logging

import async_timeout
from requests.models import PreparedRequest
import voluptuous as vol

from .const import BASE_URL
from homeassistant.components.sensor import PLATFORM_SCHEMA

# from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv

# from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import html

CONF_L = "L"
CONF_NAME = "name"
CONF_EVAID = "evaId"
CONF_BOARDTYPE = "boardType"
CONF_PRODUCTSFILTER = "productsFilter"
CONF_DIRINPUT = "dirInput"
CONF_TICKERID = "tickerID"
CONF_START = "start"
CONF_EQSTOPS = "eqstops"
CONF_SHOWJOURNEYS = "showJourneys"
CONF_ADDITIONALTIME = "additionalTime"
CONF_ICON = "icon"

SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_L, default="vs_liveticker"): cv.string,
        vol.Optional(CONF_NAME, default="oebb_journey"): cv.string,
        vol.Required(CONF_EVAID, default=None): cv.Number,
        vol.Optional(CONF_BOARDTYPE, default="dep"): cv.string,
        vol.Optional(CONF_PRODUCTSFILTER, default=1011111111011): cv.Number,
        vol.Optional(CONF_DIRINPUT, default=""): cv.Number,
        vol.Optional(CONF_TICKERID, default="dep"): cv.string,
        vol.Optional(CONF_START, default="yes"): cv.string,
        vol.Optional(CONF_EQSTOPS, default="false"): cv.string,
        vol.Optional(CONF_SHOWJOURNEYS, default=12): cv.Number, 
        vol.Optional(CONF_ADDITIONALTIME, default=0): cv.Number,
        #vol.Optional(CONF_ICON, default="mdi:tram"): cv.string,
    }
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    evaId = config.get(CONF_EVAID)
    name = config.get(CONF_NAME)
    showJourneys = config.get(CONF_SHOWJOURNEYS)

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
        "selectDate": "period",
        "dateBegin": now.strftime("%d.%m.%Y"),
        "dateEnd": tomorrow.strftime("%d.%m.%Y"),
        "outputMode": "tickerDataOnly",
    }

    # icon = config.get(CONF_ICON)
    # devices = []
    # api is my coordinator
    api = OebbAPI(async_create_clientsession(hass), hass.loop, params)
    coordinator = OebbCoordinator(hass, api)
    # data = await api.get_json()
    # _LOGGER.debug(len(data["journey"]))

    await coordinator.async_config_entry_first_refresh()

    devices = []


    journeys = coordinator.data["journey"]
    
    if(len(journeys) > 0):
        ids = []
        nr = 0
        for  journey in journeys:
            # only use unique journeys (non unique journeys happen when eqstops are existing)
            if journey["id"] not in ids:
                devices.append(OebbSensor(coordinator, journey, evaId, name, nr))
                ids.append(journey["id"])
                nr = nr + 1
            # stop if we have enough journeys (filter is not working correctly in api when specifying date filters)
            if len(ids) == showJourneys: 
                break
    else:
        _LOGGER.warning("No journeys found for EVA ID %s and name %s", evaId, name)
       
    add_devices_callback(devices, True)


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

        _LOGGER.debug("Inside Fetch_data")

        try:

            async with self.session.get(BASE_URL, params=self.params) as resp:
                text = await resp.text()
                value = json.loads(text.replace("\n", "")[13:])

        except Exception:
            pass

        return value


class OebbCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, oebb_api: OebbAPI):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="OEBB Coordinator",
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
            async with async_timeout.timeout(20):
                return await self.oebb_api.fetch_data()

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class OebbSensor(CoordinatorEntity, SensorEntity):
    """OebbSensor."""

    def __init__(self, coordinator: OebbCoordinator, journey, evaId, sensorName, sensorNr):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self.journey = journey
        self._name = sensorName + "_" + str(sensorNr)
        self._state = None
        self.attributes = {}
        #self.icon = icon

        self._attr_unique_id = sensorName + "_" + str(sensorNr)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        journey = self.journey

        self.attributes = {
            "startTime": journey["ti"],
            "startDate": journey["da"],
            "lastStop": html.unescape(journey["lastStop"]),
            "line": journey["pr"],
            "rt": journey["rt"],
        }
        now = datetime.now()

        date_string = now.strftime("%d/%m/%Y")
        # _LOGGER.debug("Date_string : %s", date_string)
        timestamp_string = date_string + " " + self.attributes["startTime"]
        # _LOGGER.debug("Timestamp_string %s:", timestamp_string)
        self._state = datetime.strptime(timestamp_string, "%d/%m/%Y %H:%M")
        # _LOGGER.debug("State: %s:", self._state)
        self.async_write_ha_state()

        # self._name = self.attributes["startTime"]

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
        return "mdi:tram"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self.attributes

    @property
    def device_class(self):
        """Return device_class."""
        return "timestamp"
