"""SOREL Connect specific constants."""
from homeassistant.helpers.entity import DeviceInfo
import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "sorel_connect"
NAME: Final = "SOREL Connect"

DEVICE_INFO: Final[DeviceInfo] = {
	"identifiers": {(DOMAIN,)},
	"model": NAME,
	"default_name": NAME,
	"manufacturer": NAME,
}

DATA_CLIENT: Final = "client"
DATA_COORDINATOR: Final = "coordinator"

MAX_SENSORS = 10
MAX_RELAYS = 5
