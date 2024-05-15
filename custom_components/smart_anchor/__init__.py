"""Smart Boat Anchor Integration. init.py"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging

DOMAIN = "smart_anchor"

_LOGGER = logging.getLogger(__name__)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Options for Smart_Anchor have been updated - applying changes")
    # Reload the integration to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: dict):
    _LOGGER.debug("Setting up Smart_Anchor integration")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Starting setup for Smart_Anchor integration with entry: %s", entry.as_dict())

    # Ensure the DOMAIN data container exists
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Data container for domain initialized")

    # Register the update listener and log this action
    unload_handle = entry.add_update_listener(update_listener)
    entry.async_on_unload(unload_handle)
    _LOGGER.debug("Update listener registered for Smart_Anchor integration")

    # Save the configuration entry to hass.data for quick access
    hass.data[DOMAIN][entry.entry_id] = entry.data
    _LOGGER.debug("Configuration entry saved: %s", entry.data)

    # Forward the setup to the device_tracker platform
    _LOGGER.debug("Forwarding setup to device_tracker platform")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "device_tracker")
    )

    # Forward the setup to the number platform
    _LOGGER.debug("Forwarding setup to number platform")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "number")
    )

    _LOGGER.debug("Setup for Smart_Anchor integration completed successfully")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Starting unload for Smart_Anchor integration with entry: %s", entry.as_dict())

    # Remove the entry from DOMAIN data container
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Entry removed from domain data container")

    # Forward the unload to the device_tracker platform and await its completion
    _LOGGER.debug("Forwarding unload to device_tracker platform")
    result = await hass.config_entries.async_forward_entry_unload(entry, "device_tracker")
    _LOGGER.debug("Unload forwarded to device_tracker platform with result: %s", result)

    # Forward the unload to the number platform and await its completion
    _LOGGER.debug("Forwarding unload to number platform")
    result = await hass.config_entries.async_forward_entry_unload(entry, "number")
    _LOGGER.debug("Unload forwarded to number platform with result: %s", result)


    _LOGGER.debug("Unload for Smart_Anchor integration completed successfully")
    return True