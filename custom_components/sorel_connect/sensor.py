from __future__ import annotations
from datetime import date, timedelta
from homeassistant.components.sensor import (
	SensorDeviceClass,
	SensorEntity,
	SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
	PERCENTAGE,
	UnitOfEnergy,
	UnitOfPower,
	UnitOfTemperature
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
	DOMAIN,
	DATA_CLIENT,
	DATA_COORDINATOR,
)
from .sorel_connect import (
	SorelConnectEnergyEntity,
	SorelConnectEnergyType,
	SorelConnectCoordinatorEntity,
	SorelConnectEntityType,
)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
	coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

	entities = []

	mapping = {
		SorelConnectEntityType.TEMPERATURE: SorelConnectTemperatureSensorEntity,
		SorelConnectEntityType.PERCENTAGE: SorelConnectPercentageSensorEntity,
		SorelConnectEntityType.POWER: SorelConnectPowerSensorEntity,
		SorelConnectEntityType.ENERGY: SorelConnectEnergySensorEntity,
	}

	for entity_type, entity_class in mapping.items():
		if entity_type not in client.entities:
			continue

		for entity in client.entities[entity_type].values():
			entities.append(entity_class(coordinator, entity))

	async_add_entities(entities)


class SorelConnectSensorEntity(SorelConnectCoordinatorEntity, SensorEntity):

	def _update_attributes(self) -> None:
		if self.coordinator.data is None:
			return

		self._attr_native_value = self.coordinator.data[self._entity.id]


class SorelConnectTemperatureSensorEntity(SorelConnectSensorEntity):

	_attr_state_class = SensorStateClass.MEASUREMENT
	_attr_device_class = SensorDeviceClass.TEMPERATURE
	_attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


class SorelConnectPercentageSensorEntity(SorelConnectSensorEntity):

	_attr_state_class = SensorStateClass.MEASUREMENT
	_attr_native_unit_of_measurement = PERCENTAGE
	_attr_native_precision = 0

class SorelConnectPowerSensorEntity(SorelConnectSensorEntity):

	_attr_state_class = SensorStateClass.MEASUREMENT
	_attr_device_class = SensorDeviceClass.POWER
	_attr_native_unit_of_measurement = UnitOfPower.WATT
	_attr_native_precision = 0

class SorelConnectEnergySensorEntity(SorelConnectSensorEntity):

	_attr_device_class = SensorDeviceClass.ENERGY
	_attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
	_attr_native_precision = 3

	def __init__(self, coordinator: DataUpdateCoordinator, entity: SorelConnectEnergyEntity) -> None:
		super().__init__(coordinator, entity)

		self._entity: SorelConnectEnergyEntity = entity

		self._attr_unique_id = self._entity.unique_id
		self._attr_name = self._entity.name

		self._attr_state_class = SensorStateClass.TOTAL_INCREASING if self._entity.energy_type == SorelConnectEnergyType.TOTAL else SensorStateClass.TOTAL
		self._attr_native_unit_of_measurement = UnitOfEnergy.MEGA_WATT_HOUR if self._entity.energy_type in (SorelConnectEnergyType.TOTAL, SorelConnectEnergyType.YEAR) else UnitOfEnergy.KILO_WATT_HOUR

		self._update_attributes()

	def _update_attributes(self) -> None:
		if self.coordinator.data is None:
			return

		value = self.coordinator.data[self._entity.id]

		if self._entity.energy_type in (SorelConnectEnergyType.TOTAL, SorelConnectEnergyType.YEAR):
			value = round(value / 1000, 3)

		self._attr_native_value = value

		if self._entity.energy_type == SorelConnectEnergyType.YEAR:
			self._attr_last_reset = date(date.today().year, 1, 1)
		elif self._entity.energy_type == SorelConnectEnergyType.MONTH:
			today = date.today()
			self._attr_last_reset = date(today.year, today.month, 1)
		elif self._entity.energy_type == SorelConnectEnergyType.WEEK:
			today = date.today()
			self._attr_last_reset = today - timedelta(days=today.weekday())
		elif self._entity.energy_type == SorelConnectEnergyType.DAY:
			self._attr_last_reset = date.today()

