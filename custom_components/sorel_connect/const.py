"""SOREL connect specific constants."""
from homeassistant.helpers.entity import DeviceInfo
import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "sorel_connect"
NAME: Final = "SOREL connect"

DEVICE_INFO: Final[DeviceInfo] = {
	"identifiers": {(DOMAIN,)},
	"model": "SOREL Connect",
	"default_name": "SOREL Connect",
	"manufacturer": NAME,
}

DATA_CLIENT: Final = "client"
DATA_COORDINATOR: Final = "coordinator"

MAX_SENSORS = 10
MAX_RELAYS = 5
