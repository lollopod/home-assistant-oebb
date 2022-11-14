"""
A integration that allows you to get information about next departure from specified stop.
For more details about this component, please refer to the documentation at
https://github.com/tofuSCHNITZEL/home-assistant-wienerlinien
"""
from datetime import timedelta
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

    devices = []

    api = OebbAPI(async_create_clientsession(hass), hass.loop, params)
    data = await api.get_json()

    for index, journey in enumerate(data["journey"]):

        try:
            name = "journey_" + index
        except Exception:
            raise PlatformNotReady()
        devices.append(OebbSensor(api, name, index))
    add_devices_callback(devices, True)


class OebbSensor(Entity):
    """OebbSensor."""

    def __init__(self, api, name, index):
        """Initialize."""
        self.api = api
        self.index = index
        self._name = name
        self._state = None
        self.attributes = {}

    async def async_update(self):
        """Update data."""
        try:
            data = await self.api.get_json()
            _LOGGER.debug(data)
            if data is None:
                return
            data = data.get("data", {})
        except:
            _LOGGER.debug("Could not get new state")
            return

        if data is None:
            return
        try:
            self.attributes = {
                "startTime": data["journey"][self.index]["ti"],
                "lastStop": data["journey"][self.index]["LastStop"],
                "line": data["journey"][self.index]["pr"],
            }

        except Exception:
            pass

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def state(self):
        """Return state."""
        if self._state is None:
            return self._state
        else:
            return f"{self._state[:-2]}:{self._state[26:]}"

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


class OebbAPI:
    """Call API."""

    def __init__(self, session, loop, params):
        """Initialize."""
        self.params = params
        self.loop = loop
        self.session = session

    async def get_json(self):
        """Get json from API endpoint."""
        value = None

        _LOGGER.debug("Inside get JSON")
        req = PreparedRequest()
        req.prepare_url(BASE_URL, self.params)
        try:
            async with async_timeout.timeout(10):

                response = await self.session.get(req.url)

            # value = json.loads(response_string[14:])

        except Exception:
            pass
        string = str(response.content._buffer[0]).replace("\\n", "")[16:-1]

        value = json.loads(string)

        return value
