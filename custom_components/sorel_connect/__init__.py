from homeassistant import config_entries, core
from homeassistant.const import Platform
from .const import (
	DATA_CLIENT,
	DATA_COORDINATOR,
	DOMAIN,
)
from .sorel_connect import (
	SorelConnectClient,
	SorelConnectCoordinator,
)


async def async_setup_entry(hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
	hass.data.setdefault(DOMAIN, {})
	hass.data[DOMAIN][config_entry.entry_id] = {}

	client = SorelConnectClient(hass, dict(config_entry.data))
	await client.initialize()

	coordinator = SorelConnectCoordinator(hass, client)
	await coordinator.async_refresh()

	hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT] = client
	hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR] = coordinator

	#for platform in (Platform.BINARY_SENSOR, Platform.SENSOR):
	platform = Platform.SENSOR
	hass.async_create_task(
		hass.config_entries.async_forward_entry_setup(config_entry, platform)
	)

	return True
