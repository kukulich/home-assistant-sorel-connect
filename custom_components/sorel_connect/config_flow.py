from __future__ import annotations
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
	CONF_ID,
	CONF_EMAIL,
	CONF_PASSWORD,
)
from homeassistant.data_entry_flow import AbortFlow
from typing import Any, Dict
import voluptuous as vol
from .const import (
	DOMAIN,
	NAME,
	LOGGER,
)
from .errors import (
	InvalidCredentials,
	ServiceUnavailable,
)
from .sorel_connect import SorelConnectClient


class SorelConnectConfigFlow(ConfigFlow, domain=DOMAIN):
	async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
		errors = {}

		if user_input is not None:

			try:
				unique_id = user_input[CONF_ID]

				await self.async_set_unique_id(unique_id)
				self._abort_if_unique_id_configured()

				client = SorelConnectClient(self.hass, user_input)
				await client.login()

				return self.async_create_entry(title=NAME, data=user_input)

			except AbortFlow as ex:
				return self.async_abort(reason=ex.reason)

			except ServiceUnavailable:
				errors["base"] = "service_unavailable"

			except InvalidCredentials:
				errors["base"] = "invalid_credentials"

			except Exception as ex:
				LOGGER.debug(format(ex))
				return self.async_abort(reason="unknown")

		return self.async_show_form(
			step_id="user",
			data_schema=vol.Schema(
				{
					vol.Required(CONF_ID): str,
					vol.Required(CONF_EMAIL): vol.All(str, vol.Length(min=1)),
					vol.Required(CONF_PASSWORD): vol.All(str, vol.Length(min=1)),
				}
			),
			errors=errors,
		)
