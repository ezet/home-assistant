"""
Support for AtB Bus information from https://atbapi.tar.io/.
"""
import logging
from datetime import timedelta, datetime
from typing import List

import pytz
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, STATE_UNKNOWN, CONF_SENSORS
from homeassistant.helpers.entity import Entity, generate_entity_id

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://atbapi.tar.io/api/v1/departures/'

ATTRIBUTION = "Data provided by https://atbapi.tar.io/"

CONF_STOP_ID = 'stop_id'
CONF_STOP_NAME = 'stop_name'
CONF_BUS_FILTER = 'bus_filter'
CONF_DEPARTURE_SENSORS = 'all_departures'

TIMEZONE = "Europe/Oslo"
tz = pytz.timezone(TIMEZONE)

ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(minutes=1)

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Optional(CONF_STOP_NAME): cv.string,
    vol.Optional(CONF_BUS_FILTER): cv.ensure_list_csv,
    vol.Optional(CONF_DEPARTURE_SENSORS, default=False): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the AtB sensors."""

    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        stop = device_config[CONF_STOP_ID]
        stop_name = device_config.get(CONF_STOP_NAME)
        bus_filter = device_config.get(CONF_BUS_FILTER)
        departure_sensors = device_config.get(CONF_DEPARTURE_SENSORS)
        stop_sensor = AtbStopSensor(hass, device, stop, stop_name, bus_filter, departure_sensors)
        sensors.append(stop_sensor)
        sensors.extend(stop_sensor.departure_sensors)

    add_entities(sensors, True)


def parse_datetime(json: str) -> str:
    """
    Parse a date string from the AtB REST API and return it's ISO representation.
    The API does not return timezone, but it is always Europe/Oslo.
    :param json: The JSON representation of a naive datetime from the AtB API.
    :return: A timezone aware ISO formatted string.
    """
    naive: datetime = datetime.fromisoformat(json)
    aware: datetime = tz.localize(naive)
    return aware.isoformat()


class AtbStopSensor(Entity):
    """
    This sensor fetches and stores all available data from the API.
    The name is fetched from the API, but can be overridden using 'name'.
    The state is the time of the next expected departure.
    """

    def __init__(self, hass, device: str, stop_id: int, stop_name: str, bus_filter: List[str], departure_sensors: bool):
        self._data = {}
        self._state = STATE_UNKNOWN
        self._stop_id = stop_id
        self._name = stop_name
        self._bus_filter = set(bus_filter) if bus_filter else None
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device, hass=hass)
        self.departure_sensors: List[AtbDepartureSensor] = []
        if departure_sensors:
            for i in range(0, 5):
                self.departure_sensors.append(AtbDepartureSensor(hass, f"{device}_{i}"))

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return 'mdi:bus-clock'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._data

    def update(self):
        """Update device state."""
        self._data = requests.get(f"{_RESOURCE}{self._stop_id}/").json()
        self._state = STATE_UNKNOWN
        for departure in self._data['departures']:
            if not self._bus_filter or int(departure['line']) in self._bus_filter:
                self._state = parse_datetime(departure['registeredDepartureTime'])
                break
        # self._state = parse_datetime(self._data['departures'][0]['registeredDepartureTime'])
        length = min(len(self._data['departures']), len(self.departure_sensors))
        for index in range(0, length):
            self.departure_sensors[index].update_sensor(self._data['departures'][index])


class AtbDepartureSensor(Entity):
    """
    This sensor exposes a single departure from a given stop.
    The name is the bus line number.
    The state is the expected time of departure.
    """

    def __init__(self, hass, device: str):
        self._name = None
        self.should_poll = False
        self._state = STATE_UNKNOWN
        self._data = None
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device, hass=hass)

    def should_poll(self) -> bool:
        """Disable polling, this sensor is updated by its parent AtbStopSensor"""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._data

    def update_sensor(self, json):
        """ Manually update the sensor"""
        self._data = json
        self._state = parse_datetime(self._data['registeredDepartureTime'])
        self._name = json['line']
        self.schedule_update_ha_state()
