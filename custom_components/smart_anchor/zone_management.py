# zone_management.py

import logging
import math
from homeassistant.core import HomeAssistant
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN, ZoneStorageCollection
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

async def update_ha_location(hass: HomeAssistant, latitude_entity: str, longitude_entity: str):
    """Update Home Assistant's location based on sensor data."""
    latitude_state = hass.states.get(latitude_entity)
    longitude_state = hass.states.get(longitude_entity)

    if not latitude_state or not longitude_state:
        _LOGGER.error("Latitude or longitude entity not found.")
        return

    try:
        latitude = float(latitude_state.state)
        longitude = float(longitude_state.state)
    except ValueError:
        _LOGGER.error("Invalid latitude or longitude values.")
        return

    # Call the set_location service to update Home Assistant's location
    await hass.services.async_call('homeassistant', 'set_location', {
        'latitude': latitude,
        'longitude': longitude
    })
    _LOGGER.info(f"Home Assistant location updated to Latitude: {latitude}, Longitude: {longitude}")


async def setup_periodic_location_updates(hass: HomeAssistant, latitude_entity: str, longitude_entity: str):
    """Setup periodic updates for Home Assistant's location."""

    async def periodic_update(now):
        """Function to run at each interval."""
        await update_ha_location(hass, latitude_entity, longitude_entity)

    update_interval = timedelta(seconds=10)
    
    cancel_callback = async_track_time_interval(hass, periodic_update, update_interval)
    return cancel_callback
    

async def ensure_zone_collection_loaded(hass: HomeAssistant):
    if ZONE_DOMAIN not in hass.data:
        hass.data[ZONE_DOMAIN] = ZoneStorageCollection(hass)
        await hass.data[ZONE_DOMAIN].async_load()


async def create_zone(hass: HomeAssistant, name: str, latitude: float, longitude: float, radius: float, heading=None, distance_to_bow=None):
    """Create a zone in Home Assistant."""
    
    if heading is not None and distance_to_bow is not None:
        latitude, longitude = calculate_new_position(latitude, longitude, heading, distance_to_bow)
        _LOGGER.info(f"Bow position calculated heading {heading} and distance {distance_to_bow} meters.")
    else:
        _LOGGER.info("No Bow position calculated.")
    
    await ensure_zone_collection_loaded(hass)

    # Prepare the zone information
    zone_info = {
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius,
        "icon": "mdi:anchor",
        "passive": False
    }

    try:
        zone_collection: ZoneStorageCollection = hass.data[ZONE_DOMAIN]
        await zone_collection.async_create_item(zone_info)
        _LOGGER.info(f"Zone '{name}' created successfully with latitude {latitude}, longitude {longitude}, and radius {radius}.")
    except Exception as e:
        _LOGGER.error(f"Error creating zone '{name}': {e}")
        raise


async def update_zone(hass: HomeAssistant, entity_id: str, name: str = None, latitude: float = None, longitude: float = None, radius: float = None, icon: str = None, passive: bool = None):
    """Update or delete a zone in Home Assistant."""
    entity_registry = er.async_get(hass)
    zone_entity = entity_registry.async_get(entity_id)

    if not zone_entity:
        _LOGGER.error(f"Zone with entity_id '{entity_id}' not found")
        raise HomeAssistantError(f"Zone with entity_id '{entity_id}' not found")

    # Check if the radius is zero to trigger deletion
    if radius == 0:
        await delete_zone(hass, zone_entity.unique_id)
        return

    await ensure_zone_collection_loaded(hass)
    zone_collection: ZoneStorageCollection = hass.data[ZONE_DOMAIN]

    zone_info = {}
    if name is not None:
        zone_info['name'] = name
    if latitude is not None:
        zone_info['latitude'] = latitude
    if longitude is not None:
        zone_info['longitude'] = longitude
    if radius is not None:
        zone_info['radius'] = radius
    if icon is not None:
        zone_info['icon'] = icon
    if passive is not None:  
        zone_info['passive'] = passive


    try:
        await zone_collection.async_update_item(zone_entity.unique_id, zone_info)
        _LOGGER.info(f"Zone '{entity_id}' updated successfully.")
    except Exception as e:
        _LOGGER.error(f"Error updating zone '{entity_id}': {e}")
        raise HomeAssistantError(f"Error updating zone '{entity_id}': {e}")


async def delete_zone(hass: HomeAssistant, unique_id: str):
    """Delete a zone from Home Assistant."""
    await ensure_zone_collection_loaded(hass)
    zone_collection: ZoneStorageCollection = hass.data[ZONE_DOMAIN]

    try:
        await zone_collection.async_delete_item(unique_id)
        _LOGGER.info(f"Zone with ID '{unique_id}' deleted successfully.")
    except Exception as e:
        _LOGGER.error(f"Error deleting zone with ID '{unique_id}': {e}")
        raise HomeAssistantError(f"Error deleting zone with ID '{unique_id}': {e}")



def calculate_new_position(latitude, longitude, heading, distance):
    """
    Calculate new latitude and longitude based on heading and distance, assuming a flat Earth.
    
    Parameters:
    - latitude (float): The starting latitude
    - longitude (float): The starting longitude
    - heading (float): The heading in degrees (where 0 degrees is north, clockwise)
    - distance (float): The distance to travel in meters

    Returns:
    - tuple: New latitude and longitude
    """
    # Earth's radius at the equator in meters
    R = 6378137
    # Convert heading to radians
    heading_rad = math.radians(heading)

    # Calculate change in coordinates
    delta_lat = distance * math.cos(heading_rad) / R
    delta_lon = distance * math.sin(heading_rad) / (R * math.cos(math.radians(latitude)))

    # Convert radians to degrees
    new_latitude = latitude + math.degrees(delta_lat)
    new_longitude = longitude + math.degrees(delta_lon)

    return (new_latitude, new_longitude)
