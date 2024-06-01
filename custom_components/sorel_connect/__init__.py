from dataclasses import dataclass
from typing import Final
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .sorel_connect import (
	SorelConnectClient,
	SorelConnectCoordinator,
)


@dataclass
class SorelConnectConfigEntryData:
	client: SorelConnectClient
	coordinator: SorelConnectCoordinator


type SorelConnectConfigEntry = ConfigEntry[SorelConnectConfigEntryData]


PLATFORMS: Final = [
	Platform.BINARY_SENSOR,
	Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: SorelConnectConfigEntry) -> bool:
	client = SorelConnectClient(hass, dict(config_entry.data))
	await client.initialize()

	coordinator = SorelConnectCoordinator(hass, client)
	await coordinator.async_config_entry_first_refresh()

	config_entry.runtime_data = SorelConnectConfigEntryData(client, coordinator)

	for platform in PLATFORMS:
		hass.async_create_task(
			hass.config_entries.async_forward_entry_setup(config_entry, platform)
		)

	return True


async def async_unload_entry(hass: HomeAssistant, config_entry: SorelConnectConfigEntry) -> bool:
	return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
