from __future__ import annotations
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
	hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:

	return {
		"configuration": async_redact_data(config_entry.data, CONF_PASSWORD),
	}
