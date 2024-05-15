"""Smart Boat Anchor Integration. number.py"""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import NumberEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, ZONE_ID, HELPER_FIELD_ID, HELPER_FIELD_NAME

from .device_tracker import ensure_zone_collection_loaded


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    
    
    _LOGGER.debug("In async_setup_entry number.py.")

     # Save a reference to the add_entities callback
    hass.data[DOMAIN]["async_add_entities"] = async_add_entities

    # Create the input_number helper

    current_radius = await find_zone_radius(hass)
    
    new_number = InputNumber(HELPER_FIELD_ID,current_radius)    
    
    domain_data = hass.data.setdefault(DOMAIN, {})

    domain_data['async_add_entities']([new_number])
    domain_data[HELPER_FIELD_ID] = new_number
    
    _LOGGER.info(f"Created new number entity {HELPER_FIELD_ID}")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    
    _LOGGER.debug("In async_unload_entry number.py.")

    return True


async def find_zone_radius(hass: HomeAssistant):
      
    zone_entity_id = ZONE_ID

    entity_registry = er.async_get(hass)
    zone_entity = entity_registry.async_get(zone_entity_id)

    if not zone_entity:
        default_radius = hass.data[DOMAIN]["default_radius"]
        _LOGGER.debug(f"Zone with entity_id {zone_entity_id} not found. Using default radius")
        return default_radius

    await ensure_zone_collection_loaded(hass)
       
    zone_state = hass.states.get(zone_entity_id)
    
    if zone_state:
        radius = zone_state.attributes.get('radius')
        passive = zone_state.attributes.get('passive')
        
        if passive:
            default_radius = hass.data[DOMAIN]["default_radius"]
            _LOGGER.debug(f"Zone with entity_id {zone_entity_id} is passive. Using default radius")
            return default_radius

        if radius is not None:
            _LOGGER.debug(f"The radius of the zone '{zone_entity_id}' is currently {radius} meters.")
            return radius
        else:
            _LOGGER.warning(f"Radius attribute not found for the zone '{zone_entity_id}'.")
            return 0
    else:
        _LOGGER.warning(f"Zone state for '{zone_entity_id}' could not be retrieved.")
        return 0



class InputNumber(NumberEntity):
    
    _attr_icon = "mdi:location-exit"

    def __init__(self, name, initial_value):        
        self._attr_id = name
        self._attr_name = HELPER_FIELD_NAME
        self._attr_native_value = int(initial_value)
        self._attr_editable = True
        self._attr_mode = 'box'
        self._attr_native_min_value = 1
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_device_class = "distance"  
        self._attr_native_unit_of_measurement = "m"

    @property
    def native_value(self):      
        return int(self._attr_native_value)


    async def async_set_native_value(self, value):
        if value is None or not (self._attr_native_min_value <= int(value) <= self._attr_native_max_value):
            # Log the error
            _LOGGER.error(f"Invalid input: {value}. Value must be between {self._attr_native_min_value} and {self._attr_native_max_value}.")
            # Raise HomeAssistantError
            raise HomeAssistantError(f"Invalid input: {value}. Value must be between {self._attr_native_min_value} and {self._attr_native_max_value}.")
        
        self._attr_native_value = int(value)
        self.async_write_ha_state()
        
    @property
    def native_min_value(self):        
        return self._attr_native_min_value

    @property
    def native_max_value(self):
        return self._attr_native_max_value

    @property
    def native_step(self):
        return self._attr_native_step

    @property
    def mode(self):        
        return self._attr_mode

    @property
    def native_unit_of_measurement(self):
        return self._attr_native_unit_of_measurement
