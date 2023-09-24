from __future__ import annotations
import aiohttp
from abc import abstractmethod
from datetime import timedelta
from enum import Enum, StrEnum
from homeassistant.const import (
	CONF_ID,
	CONF_EMAIL,
	CONF_PASSWORD,
	STATE_ON,
	STATE_OFF,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import (
	aiohttp_client,
	storage,
)
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
	CoordinatorEntity,
	DataUpdateCoordinator,
)
from json import loads as json_load
from http import HTTPStatus
from http.cookies import SimpleCookie
import re
from typing import Any, Dict, Final
from .const import (
	DEVICE_INFO,
	DOMAIN,
	LOGGER,
	MAX_RELAYS,
	MAX_SENSORS,
)
from .errors import (
	InvalidCredentials,
	ServiceUnavailable,
)

STORAGE_VERSION: Final = 1
STORAGE_SENSORS_KEY: Final = "sensors"

class SorelConnectEntityType(StrEnum):
	TEMPERATURE = "temperature"
	PERCENTAGE = "percent"
	ON_OFF = "on_off"
	POWER = "power"
	ENERGY = "energy"


class SorelConnectEntity:

	def __init__(self, entity_unique_id: str, entity_type: SorelConnectEntityType, entity_id: str, entity_name: str) -> None:
		self.unique_id: str = entity_unique_id
		self.type: SorelConnectEntityType = entity_type
		self.id: str = entity_id
		self.name: str = entity_name


class SorelConnectPowerType(Enum):
	ACTUAL = 17
	DAY = 18
	WEEK = 19
	MONTH = 20
	YEAR = 21
	TOTAL = 22


class SorelConnectEnergyType(StrEnum):
	DAY = "day"
	WEEK = "week"
	MONTH = "month"
	YEAR = "year"
	TOTAL = "total"


class SorelConnectEnergyEntity(SorelConnectEntity):

	def __init__(self, entity_unique_id: str, entity_id: str, entity_name: str, energy_type: SorelConnectEnergyType) -> None:
		super().__init__(entity_unique_id, SorelConnectEntityType.ENERGY, entity_id, entity_name)

		self.energy_type: SorelConnectEnergyType = energy_type


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
		await self._detect_and_create_power_and_energy_sensors()
		await self._detect_and_create_relays()

	async def update_data(self) -> Dict[str, StateType]:
		await self.login()

		await self._update_sensors_states()
		await self._update_power_and_energy_sensors_states()
		await self._update_relays_states()

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

	async def _detect_and_create_relays(self) -> None:
		for relay_id in range(1, MAX_RELAYS + 1):
			relay_raw_value = await self._get_relay_raw_value(relay_id)
			if relay_raw_value is None:
				continue

			entity_type = self._detect_entity_type_from_relay_value(relay_id, relay_raw_value)

			if entity_type is None:
				continue

			self._create_entity(
				entity_type,
				self._get_entity_relay_id(relay_id),
				self._get_entity_relay_name(relay_id),
				self._get_entity_value_from_relay_value(relay_id, relay_raw_value),
			)

	async def _update_relays_states(self) -> None:
		for relay_id in range(1, MAX_RELAYS + 1):
			relay_raw_value = await self._get_relay_raw_value(relay_id)

			if relay_raw_value is None:
				continue

			self._entities_states[self._get_entity_relay_id(relay_id)] = self._get_entity_value_from_relay_value(relay_id, relay_raw_value)

	async def _get_relay_raw_value(self, relay_id: int) -> StateType:
		response = await self._logged_request(self._get_relay_url(relay_id))

		return await self._get_value_from_response(response)

	@staticmethod
	def _detect_entity_type_from_relay_value(relay_id: int, relay_raw_value: str) -> SorelConnectEntityType | None:
		if re.match("^\d+_(OFF|ON)$", relay_raw_value):
			return SorelConnectEntityType.ON_OFF

		if re.match("^(\d+)_(\d+)%$", relay_raw_value):
			return SorelConnectEntityType.PERCENTAGE

		LOGGER.debug("Unknown type of relay {}: {}", relay_id, relay_raw_value)
		return None

	@staticmethod
	def _get_entity_value_from_relay_value(relay_id: int, relay_raw_value: str) -> StateType | None:
		on_off_match = re.match("^\d+_(OFF|ON)$", relay_raw_value)
		if on_off_match:
			return STATE_ON if on_off_match.group(1) == "ON" else STATE_OFF

		percent_match = re.match("^\d+_(\d+)%$", relay_raw_value)
		if percent_match:
			return float(percent_match.group(1))

		LOGGER.debug("Unknown value of relay {}: {}", relay_id, relay_raw_value)
		return None

	async def _detect_and_create_sensors(self) -> None:
		sensors_to_check = self._sensors_count if self._sensors_count is not None else MAX_SENSORS

		self._sensors_count = 0
		for sensor_id in range(1, sensors_to_check + 1):
			sensor_value = await self._get_sensor_value(sensor_id)
			if sensor_value is None:
				break

			self._create_entity(
				SorelConnectEntityType.TEMPERATURE,
				self._get_entity_sensor_id(sensor_id),
				self._get_entity_sensor_name(sensor_id),
				sensor_value
			)
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
		value = await self._get_value_from_response(response)

		if value is None:
			return None

		match = re.match("^(-?\d+)°C$", value)

		return float(match.group(1))

	async def _detect_and_create_power_and_energy_sensors(self) -> None:
		for power_type in (SorelConnectPowerType.ACTUAL, SorelConnectPowerType.DAY, SorelConnectPowerType.WEEK, SorelConnectPowerType.MONTH, SorelConnectPowerType.YEAR, SorelConnectPowerType.TOTAL):
			power_sensor_raw_value = await self._get_power_sensor_raw_value(power_type.value)
			if power_sensor_raw_value is None:
				break

			if power_type == SorelConnectPowerType.ACTUAL:
				self._create_entity(
					SorelConnectEntityType.POWER,
					self._get_entity_power_sensor_id(power_type),
					self._get_entity_power_sensor_name(),
					self._get_entity_value_from_power_sensor_raw_value(power_type, power_sensor_raw_value),
				)
			else:
				energy_type = self._get_entity_energy_type_from_power_type(power_type)

				self._create_energy_entity(
					energy_type,
					self._get_entity_energy_sensor_id(energy_type),
					self._get_entity_energy_sensor_name(energy_type),
					self._get_entity_value_from_energy_sensor_raw_value(power_type, power_sensor_raw_value),
				)

	async def _update_power_and_energy_sensors_states(self) -> None:
		for power_type in (SorelConnectPowerType.ACTUAL, SorelConnectPowerType.DAY, SorelConnectPowerType.WEEK, SorelConnectPowerType.MONTH, SorelConnectPowerType.YEAR, SorelConnectPowerType.TOTAL):
			power_sensor_raw_value = await self._get_power_sensor_raw_value(power_type.value)
			if power_sensor_raw_value is None:
				continue

			if power_type == SorelConnectPowerType.ACTUAL:
				entity_id = self._get_entity_power_sensor_id(power_type)
				entity_value = self._get_entity_value_from_power_sensor_raw_value(power_type, power_sensor_raw_value)
			else:
				energy_type = self._get_entity_energy_type_from_power_type(power_type)
				entity_id = self._get_entity_energy_sensor_id(energy_type)
				entity_value = self._get_entity_value_from_energy_sensor_raw_value(power_type, power_sensor_raw_value)

			self._entities_states[entity_id] = entity_value

	async def _get_power_sensor_raw_value(self, sensor_id: int) -> StateType:
		response = await self._logged_request(self._get_power_sensor_url(sensor_id))

		return await self._get_value_from_response(response)

	@staticmethod
	def _get_entity_value_from_power_sensor_raw_value(power_type: SorelConnectPowerType, power_sensor_raw_value: str) -> StateType | None:
		match = re.match("^(\d+(?:\.\d+)?)(k)?W($)", power_sensor_raw_value)

		if match is None:
			LOGGER.debug("Invalid value {} of power type {}".format(power_sensor_raw_value, power_type))
			return None

		value = float(match.group(1))

		if match.group(2) == "k":
			return value * 1000

		return value

	@staticmethod
	def _get_entity_value_from_energy_sensor_raw_value(power_type: SorelConnectPowerType, power_sensor_raw_value: str) -> StateType | None:
		match = re.match("^(\d+(?:\.\d+)?)([kM])?Wh($)", power_sensor_raw_value)

		if match is None:
			LOGGER.debug("Invalid value {} of energy type {}".format(power_sensor_raw_value, power_type))
			return None

		value = float(match.group(1))

		if match.group(2) == "":
			return round(value / 1000, 3)

		if match.group(2) == "M":
			return value * 1000

		return value

	@staticmethod
	async def _get_value_from_response(response: aiohttp.ClientResponse) -> str | None:
		# The URL returns "text/html" so ignore content_type check
		data = await response.json(content_type=None)

		if (
			"response" not in data
			or "val" not in data["response"]
		):
			LOGGER.error("Invalid data {}".format(data))
			return None

		if data["response"]["val"] == "--":
			# Disabled
			return None

		return data["response"]["val"]

	def _create_energy_entity(self, energy_type: SorelConnectEnergyType, entity_id: str, entity_name: str, entity_value: StateType) -> None:
		entity = SorelConnectEnergyEntity(
			"{}.{}".format(self._config[CONF_ID], entity_id),
			entity_id,
			entity_name,
			energy_type,
		)

		self._add_entity(SorelConnectEntityType.ENERGY, entity, entity_value)

	def _create_entity(self, entity_type: SorelConnectEntityType, entity_id: str, entity_name: str, entity_value: StateType) -> None:
		entity = SorelConnectEntity(
			"{}.{}".format(self._config[CONF_ID], entity_id),
			entity_type,
			entity_id,
			entity_name,
		)

		self._add_entity(entity_type, entity, entity_value)

	def _add_entity(self, entity_type: SorelConnectEntityType, entity: SorelConnectEntity, entity_value: StateType):
		if entity_type not in self.entities:
			self.entities[entity_type] = {}

		self.entities[entity_type][entity.id] = entity

		self._entities_states[entity.id] = entity_value

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

	def _get_power_sensor_url(self, power_sensor_id: int) -> str:
		return "https://{}/heat.json?id={}".format(
			self._get_host(),
			power_sensor_id,
		)

	def _get_relay_url(self, relay_id: int) -> str:
		return "https://{}/relays.json?id={}".format(
			self._get_host(),
			relay_id,
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

	@staticmethod
	def _get_entity_power_sensor_id(power_type: SorelConnectPowerType) -> str:
		return "power_sensor_{}".format(power_type.value)

	@staticmethod
	def _get_entity_power_sensor_name() -> str:
		return "Actual power"

	@staticmethod
	def _get_entity_energy_sensor_id(energy_type: SorelConnectEnergyType) -> str:
		return "energy_sensor_{}".format(energy_type.value)

	@staticmethod
	def _get_entity_energy_sensor_name(energy_type: SorelConnectEnergyType) -> str:
		return "{} energy".format(energy_type.value[0:1].upper() + energy_type.value[1:])

	@staticmethod
	def _get_entity_energy_type_from_power_type(power_type: SorelConnectPowerType) -> SorelConnectEnergyType:
		if power_type == SorelConnectPowerType.DAY:
			return SorelConnectEnergyType.DAY

		if power_type == SorelConnectPowerType.WEEK:
			return SorelConnectEnergyType.WEEK

		if power_type == SorelConnectPowerType.MONTH:
			return SorelConnectEnergyType.MONTH

		if power_type == SorelConnectPowerType.YEAR:
			return SorelConnectEnergyType.YEAR

		return SorelConnectEnergyType.TOTAL

	@staticmethod
	def _get_entity_relay_id(relay_id: int) -> str:
		return "relay_{}".format(relay_id)

	@staticmethod
	def _get_entity_relay_name(relay_id: int) -> str:
		return "Relay {}".format(relay_id)


class SorelConnectCoordinator(DataUpdateCoordinator):

	def __init__(self, hass: HomeAssistant, client: SorelConnectClient) -> None:
		super().__init__(hass, LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5), update_method=self.update)

		self._client: SorelConnectClient = client

	async def update(self) -> Dict[str, StateType]:
		return await self._client.update_data()


class SorelConnectCoordinatorEntity(CoordinatorEntity):

	def __init__(self, coordinator: DataUpdateCoordinator, entity: SorelConnectEntity) -> None:
		super().__init__(coordinator)

		self._entity: SorelConnectEntity = entity

		self._attr_device_info = DEVICE_INFO
		self._attr_unique_id = self._entity.unique_id
		self._attr_name = self._entity.name

		self._update_attributes()

	@abstractmethod
	def _update_attributes(self) -> None:
		"""Not implemented"""

	@callback
	def _handle_coordinator_update(self) -> None:
		self._update_attributes()
		super()._handle_coordinator_update()
