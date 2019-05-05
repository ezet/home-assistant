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

TIMEZONE = "Europe/Oslo"
tz = pytz.timezone(TIMEZONE)

ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(minutes=1)

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Optional(CONF_STOP_NAME): cv.string,
    # vol.Optional(CONF_BUS_FILTER): cv.ensure_list_csv,
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
        stop_sensor = AtbStopSensor(hass, device, stop, stop_name)
        sensors.append(stop_sensor)
        sensors.extend(stop_sensor.departure_sensors)

    add_entities(sensors, True)





def parse_datetime(json: str) -> str:
    naive: datetime = datetime.fromisoformat(json)
    aware: datetime = tz.localize(naive)
    return aware.isoformat()


class AtbStopSensor(Entity):

    def __init__(self, hass, device, stop_id, stop_name):
        self._data = {}
        self._state = STATE_UNKNOWN
        self._stop_id = stop_id
        self._name = stop_name
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device, hass=hass)
        self.departure_sensors: List[AtbDepartureSensor] = []
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
        self._state = parse_datetime(self._data['departures'][0]['registeredDepartureTime'])
        length = min(len(self._data['departures']), len(self.departure_sensors))
        for index in range(0, length):
            self.departure_sensors[index].update_state(self._data['departures'][index])


class AtbDepartureSensor(Entity):

    def __init__(self, hass, device: str):
        self._name = None
        self.should_poll = False
        self._state = STATE_UNKNOWN
        self._data = None
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device, hass=hass)

    def should_poll(self) -> bool:
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

    def update_state(self, json):
        self._data = json
        self._state = parse_datetime(self._data['registeredDepartureTime'])
        self._name = json['line']
        self.schedule_update_ha_state()
