import unittest
from datetime import datetime

import requests_mock

from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, load_fixture

VALID_CONFIG = {
    'platform': 'atb',
    'sensors': {
        'atb_main_sensor': {
            'stop_id': 16010480,
            'stop_name': 'atb_stop_name',
            'all_departures': True
        }
    }
}


class TestAtbStopSensors(unittest.TestCase):

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_sensor(self, mock_req):
        mock_req.get(requests_mock.ANY, text=load_fixture('atb_departures.json'))
        assert setup_component(self.hass, 'sensor', VALID_CONFIG)

        state = self.hass.states.get('sensor.atb_stop')

        assert type(state.state) == datetime
        assert state['isGoingTowardsCentrum'] is False

        departure_1 = self.hass.states.get('sensor.atb_stop_0')
        departure_2 = self.hass.states.get('sensor.atb_stop_1')
        departure_3 = self.hass.states.get('sensor.atb_stop_2')
        departure_4 = self.hass.states.get('sensor.atb_stop_3')
        departure_5 = self.hass.states.get('sensor.atb_stop_4')
