from __future__ import annotations
from homeassistant.components.sensor import (
	SensorDeviceClass,
	SensorEntity,
	SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import (
	callback,
	HomeAssistant,
)
from homeassistant.helpers.update_coordinator import (
	CoordinatorEntity,
	DataUpdateCoordinator,
)
from .const import (
	DOMAIN,
	DATA_CLIENT,
	DATA_COORDINATOR,
)
from .sorel_connect import (
	SorelConnectEntity,
	SorelConnectEntityType,
)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
	coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

	entities = []

	for entity in client.entities[SorelConnectEntityType.TEMPERATURE].values():
		entities.append(SorelConnectSensorEntity(coordinator, entity))

	async_add_entities(entities)


class SorelConnectSensorEntity(CoordinatorEntity, SensorEntity):

	_attr_state_class = SensorStateClass.MEASUREMENT
	_attr_device_class = SensorDeviceClass.TEMPERATURE
	_attr_native_unit_of_measurement = TEMP_CELSIUS

	def __init__(self, coordinator: DataUpdateCoordinator, entity: SorelConnectEntity) -> None:
		super().__init__(coordinator)

		self._entity: SorelConnectEntity = entity

		self._attr_unique_id = self._entity.unique_id
		self._attr_name = self._entity.name

		self._update_attributes()

	def _update_attributes(self) -> None:
		if self.coordinator.data is None:
			return

		self._attr_native_value = self.coordinator.data[self._entity.id]

	@callback
	def _handle_coordinator_update(self) -> None:
		self._update_attributes()
		super()._handle_coordinator_update()
