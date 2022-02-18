from __future__ import annotations
import aiohttp
from datetime import timedelta
from homeassistant.backports.enum import StrEnum
from homeassistant.const import (
	CONF_ID,
	CONF_EMAIL,
	CONF_PASSWORD,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import (
	aiohttp_client,
	storage,
)
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from json import loads as json_load
from http import HTTPStatus
from http.cookies import SimpleCookie
import re
from typing import Any, Dict, Final
from .const import (
	DOMAIN,
	LOGGER,
	MAX_SENSORS,
)
from .errors import (
	InvalidCredentials,
	ServiceUnavailable,
)

STORAGE_VERSION: Final = 1
STORAGE_SENSORS_KEY: Final = "sensors"

class SorelConnectEntityType(StrEnum):
	TEMPERATURE = 'temperature'


class SorelConnectEntity:
	def __init__(self, entity_unique_id: str, entity_type: SorelConnectEntityType, entity_id: str, entity_name: str) -> None:
		self.unique_id: str = entity_unique_id
		self.type: SorelConnectEntityType = entity_type
		self.id: str = entity_id
		self.name: str = entity_name


class SorelConnectClient:

	def __init__(self, hass: HomeAssistant, config: Dict[str, Any]) -> None:
		self._hass: HomeAssistant = hass
		self._config: Dict[str, Any] = config

		self._session: aiohttp.ClientSession = aiohttp_client.async_get_clientsession(self._hass)
		self._cookies: SimpleCookie | None = None

		self._store: storage.Store = storage.Store(self._hass, STORAGE_VERSION, DOMAIN)
		self._stored_data: dict | None = None
		self._sensors_count: int | None = None

		self.entities: Dict[SorelConnectEntityType, Dict[str, SorelConnectEntity]] = {}
		self._entities_states: Dict[str, StateType] = {}

	async def login(self) -> None:
		if self._cookies is not None:
			return

		response = await self._request(self._get_login_url())
		data = await response.text()
		json = json_load(data.strip('()'))

		if "session_key" not in json:
			raise InvalidCredentials

		self._cookies = response.cookies

	async def initialize(self) -> None:
		await self._load_stored_data()

		await self.login()
		await self._detect_and_create_sensors()
		await self._detect_and_create_sensors()

	async def update_data(self) -> Dict[str, StateType]:
		await self.login()

		await self._update_sensors_states()

		return self._entities_states

	async def _load_stored_data(self) -> None:
		self._stored_data = await self._store.async_load()

		if self._stored_data is None:
			self._stored_data = {}

		if self._config[CONF_ID] not in self._stored_data:
			return

		if STORAGE_SENSORS_KEY not in self._stored_data[self._config[CONF_ID]]:
			return

		self._sensors_count = self._stored_data[self._config[CONF_ID]][STORAGE_SENSORS_KEY]

	@callback
	def _data_to_store(self) -> dict:
		return self._stored_data

	async def _detect_and_create_sensors(self) -> None:
		await self.login()

		sensors_to_check = self._sensors_count if self._sensors_count is not None else MAX_SENSORS

		self._sensors_count = 0
		for sensor_id in range(1, sensors_to_check + 1):
			sensor_value = await self._get_sensor_value(sensor_id)
			if sensor_value is None:
				break

			self._create_sensor(sensor_id, sensor_value)
			self._sensors_count += 1

		if self._config[CONF_ID] not in self._stored_data:
			self._stored_data[self._config[CONF_ID]] = {}

		self._stored_data[self._config[CONF_ID]][STORAGE_SENSORS_KEY] = self._sensors_count
		self._store.async_delay_save(self._data_to_store)

	def _create_sensor(self, sensor_id: int, sensor_value: StateType) -> None:
		if SorelConnectEntityType.TEMPERATURE not in self.entities:
			self.entities[SorelConnectEntityType.TEMPERATURE] = {}

		entity_sensor_id = self._get_entity_sensor_id(sensor_id)
		self.entities[SorelConnectEntityType.TEMPERATURE][entity_sensor_id] = SorelConnectEntity(
			"{}.{}".format(self._config[CONF_ID], entity_sensor_id),
			SorelConnectEntityType.TEMPERATURE,
			entity_sensor_id,
			self._get_entity_sensor_name(sensor_id),
		)

		self._entities_states[entity_sensor_id] = sensor_value

	async def _update_sensors_states(self) -> None:
		for sensor_id in range(1, self._sensors_count + 1):
			self._entities_states[self._get_entity_sensor_id(sensor_id)] = await self._get_sensor_value(sensor_id)

	async def _get_sensor_value(self, sensor_id: int) -> StateType:
		response = await self._logged_request(self._get_sensor_url(sensor_id))

		# The URL returns "text/html" so ignore content_type check
		sensor_data = await response.json(content_type=None)

		if (
			"response" not in sensor_data
			or "val" not in sensor_data["response"]
		):
			LOGGER.error("Invalid data {} for sensor {}".format(sensor_data, sensor_id))
			return None

		if sensor_data["response"]["val"] == "--":
			# Disabled sensor
			return None

		match = re.match("^(\d+)°C$", sensor_data["response"]["val"])

		return float(match.group(1))

	def _get_host(self) -> str:
		return "{}.sorel-connect.net".format(self._config[CONF_ID])

	def _get_login_url(self) -> str:
		return "https://{}/nabto/hosted_plugin/login/execute?email={}&password={}".format(
			self._get_host(),
			self._config[CONF_EMAIL],
			self._config[CONF_PASSWORD],
		)

	def _get_sensor_url(self, sensor_id: int) -> str:
		return "https://{}/sensors.json?id={}".format(
			self._get_host(),
			sensor_id,
		)

	async def _logged_request(self, url: str) -> aiohttp.ClientResponse:
		response = await self._request(url, self._cookies)

		text = await response.text()
		if text.strip()[0:1] == "<":
			self._cookies = None
			await self.login()

		return await self._request(url, self._cookies)

	async def _request(self, url: str, cookies: SimpleCookie | None = None) -> aiohttp.ClientResponse:
		response = await self._session.get(url, verify_ssl=False, cookies=cookies)

		if response.status != HTTPStatus.OK:
			raise ServiceUnavailable

		return response

	@staticmethod
	def _get_entity_sensor_id(sensor_id: int) -> str:
		return "sensor_{}".format(sensor_id)

	@staticmethod
	def _get_entity_sensor_name(sensor_id: int) -> str:
		return "Sensor {}".format(sensor_id)


class SorelConnectCoordinator(DataUpdateCoordinator):

	def __init__(self, hass: HomeAssistant, client: SorelConnectClient) -> None:
		super().__init__(hass, LOGGER, name=DOMAIN, update_interval=timedelta(minutes=10), update_method=self.update)

		self._client: SorelConnectClient = client

	async def update(self) -> Dict[str, StateType]:
		return await self._client.update_data()
