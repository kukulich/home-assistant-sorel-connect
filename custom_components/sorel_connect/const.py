"""SOREL connect specific constants."""
import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "sorel_connect"
NAME: Final = "SOREL connect"

DATA_CLIENT: Final = "client"
DATA_COORDINATOR: Final = "coordinator"

MAX_SENSORS = 10
MAX_RELAYS = 5
