"""SOREL Connect specific constants."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "sorel_connect"
NAME: Final = "SOREL Connect"

DEVICE_INFO: Final = DeviceInfo(
	identifiers={(DOMAIN,)},
	model=NAME,
	name=NAME,
	manufacturer=NAME,
	entry_type=DeviceEntryType.SERVICE,
)

MAX_SENSORS = 10
MAX_RELAYS = 5
