"""Smart Boat Anchor Integration. config_flow.py"""

import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

DOMAIN = "smart_anchor"

_LOGGER = logging.getLogger(__name__)


class SmartAnchorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    
    @staticmethod
    @callback
    def async_has_single_instance(hass):
        """Return True if singleton instance already exists."""
        return bool(hass.config_entries.async_entries(DOMAIN))
  

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        
        # Check if already configured
        if self.async_has_single_instance(self.hass):
            return self.async_abort(reason="single_instance_allowed")
        
        
        if user_input is not None:
            # Create the entry with initial data
            return self.async_create_entry(title="Smart Anchor", data=user_input)

        schema = vol.Schema({
            vol.Required("latitude_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required("longitude_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required("default_radius", default=50): int,

            vol.Optional("heading_entity"): selector.EntitySelector(
               selector.EntitySelectorConfig(domain="sensor")
           ),
            vol.Optional("distance_to_bow"): int,
            
            
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SmartAnchorOptionsFlow(config_entry)

class SmartAnchorOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("Processing user input")
    
            _LOGGER.debug("Received user_input: %s", user_input)
    
            new_data = {**self.config_entry.data, **user_input}
            _LOGGER.debug("New data after processing user_input: %s", new_data)
    
            # Update the config entry with new data.
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data
            )
            
            _LOGGER.debug("data updated with user input. New data: %s", new_data)
            
            return self.async_create_entry(title="", data=None)


        schema = vol.Schema({
            vol.Required("latitude_entity", default=self.config_entry.data.get("latitude_entity")): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required("longitude_entity", default=self.config_entry.data.get("longitude_entity")): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required("default_radius", default=self.config_entry.data.get("default_radius")): int,
            vol.Optional("heading_entity", default=self.config_entry.data.get("heading_entity")): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional("distance_to_bow", default=self.config_entry.data.get("distance_to_bow")): int,
        })

        return self.async_show_form(step_id="init", data_schema=schema)