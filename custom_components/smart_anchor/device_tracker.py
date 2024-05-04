"""Smart Boat Anchor Integration. device_tracker.py"""

import logging
import math
from homeassistant.core import HomeAssistant
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN, ZoneStorageCollection
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from datetime import datetime, timedelta
from homeassistant.components.device_tracker.config_entry import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback



_LOGGER = logging.getLogger(__name__)

# Set up a time threshold for logging the same error 
ERROR_LOG_THRESHOLD = timedelta(minutes=10)
last_error_log_time = None

DOMAIN = "smart_anchor"

def setup_or_update_config(hass: HomeAssistant, entry: ConfigEntry):
    """Set up or update the configuration data."""
    _LOGGER.debug("Starting setup/update of Smart Anchor")
    _LOGGER.debug(f"Config entry data: {entry.data}")

    hass.data[DOMAIN] = {
        "latitude_entity": entry.data["latitude_entity"],
        "longitude_entity": entry.data["longitude_entity"],
        "default_radius": entry.data["default_radius"],
        "heading_entity": entry.data.get("heading_entity"),
        "distance_to_bow": entry.data.get("distance_to_bow")
    }

    _LOGGER.debug(f"Smart Anchor configuration stored: {hass.data[DOMAIN]}")


async def delete_anchor_zone(hass: HomeAssistant):
    """Delete the anchor zone."""
    zone_entity_id = "zone.anchor_zone"
    entity_reg = er.async_get(hass)
    zone_entity = entity_reg.async_get(zone_entity_id)

    if zone_entity:
        try:
            await delete_zone(hass, "anchor_zone")
            _LOGGER.debug(f"Deleted existing zone: {zone_entity_id}")
        except Exception as e:
            _LOGGER.error(f"Error deleting zone: {e}")
    else:
        _LOGGER.debug("No existing zone found to delete.")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    
    _LOGGER.debug("In async_setup_entry.")

    setup_or_update_config(hass, entry)
    
    entry.async_on_unload(entry.add_update_listener(update_listener))
       
    hass.data[DOMAIN]['ha_location_cancellation'] = await setup_periodic_location_updates(
        hass, 
        hass.data[DOMAIN]["latitude_entity"], 
        hass.data[DOMAIN]["longitude_entity"]
    )

     # Save a reference to the add_entities callback
    hass.data[DOMAIN]["async_add_entities"] = async_add_entities

    _LOGGER.debug("Periodic location HA update started.")
   
           


    async def handle_drop_anchor(call):

        """Manage the zone by deleting the existing one and optionally creating a new one."""
        _LOGGER.debug("Drop Anchor Service.")
        
        # Use the passed 'radius' or default to 'default_radius' if not provided
        default_radius = hass.data[DOMAIN]["default_radius"]
        radius = call.data.get('radius', default_radius)
        
        latitude_entity = hass.data[DOMAIN]["latitude_entity"]
        longitude_entity = hass.data[DOMAIN]["longitude_entity"]
        heading_entity = hass.data[DOMAIN]["heading_entity"]

        latitude_state = hass.states.get(latitude_entity)
        longitude_state = hass.states.get(longitude_entity)
        heading_state = hass.states.get(heading_entity) if heading_entity else None
        distance_to_bow = hass.data[DOMAIN].get("distance_to_bow")        
        
        if not latitude_state or not longitude_state or latitude_state.state == 'unavailable' or longitude_state.state == 'unavailable':
            _LOGGER.error("Latitude or longitude data is unavailable.")
            return

        try:
            latitude = float(latitude_state.state)
            longitude = float(longitude_state.state)
        except ValueError as e:
            _LOGGER.error(f"Error converting state to float: {e}")
            return

        # Convert heading to float if it's available and not 'unavailable'
        heading = float(heading_state.state) if heading_state and heading_state.state not in ['unknown', 'unavailable'] else None


        await delete_anchor_zone(hass)     
        
        try:
            _LOGGER.info(f"Call create zone with (Lat {latitude}, Lon {longitude}, heading {heading}, distance to bow {distance_to_bow}) with radius {radius} meters.")

            await create_zone(hass, "Anchor Zone", latitude, longitude, radius, heading, distance_to_bow)
            _LOGGER.info(f"Anchor zone set at (Lat {latitude}, Lon {longitude}, heading {heading}, distance to bow {distance_to_bow}) with radius {radius} meters.")
            
        except Exception as e:
            _LOGGER.error(f"Error creating zone: {e}")
            
    
        _LOGGER.info("Drop anchor service processed.")


    async def handle_lift_anchor(call):
        """Handle the lift_anchor service call."""
        _LOGGER.debug("Lift Anchor Service.")

        await delete_anchor_zone(hass)     
        _LOGGER.info("Lift anchor service processed.")


    # Register the services
    hass.services.async_register(DOMAIN, "lift_anchor", handle_lift_anchor)
    hass.services.async_register(DOMAIN, "drop_anchor", handle_drop_anchor)

    _LOGGER.debug("Smart Anchor services registered")
    _LOGGER.debug("Smart Anchor setup completed successfully")
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.info("Configuration has been updated.")
    # Update the internal configuration data using the same function
    setup_or_update_config(hass, entry)



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    
    _LOGGER.debug("In async_unload_entry.")

    try:
        if 'ha_location_cancellation' in hass.data[DOMAIN]:
            hass.data[DOMAIN]['ha_location_cancellation']()  
            _LOGGER.debug("Canceled the periodic location updates.")
            hass.data[DOMAIN].pop('ha_location_cancellation')
            _LOGGER.debug("Periodic location HA update stopped.")

        await delete_anchor_zone(hass)     

        hass.services.async_remove(DOMAIN, "lift_anchor")
        hass.services.async_remove(DOMAIN, "drop_anchor")

        if DOMAIN in hass.data:
            del hass.data[DOMAIN]

        return True
    except Exception as e:
        _LOGGER.error(f"Failed to unload the integration: {str(e)}")
        return False


async def handle_new_location_data(hass, latitude, longitude):
    """Handle incoming location data by updating or creating a tracker entity."""
    domain_data = hass.data.setdefault('smart_anchor', {})
    tracker_key = "boat_location"

    try:
        if tracker_key in domain_data:
            # The entity exists, update its location
            tracker = domain_data[tracker_key]
            _LOGGER.debug(f"Updating location for {tracker_key} to latitude={latitude}, longitude={longitude}")
            tracker.update_location(latitude, longitude)
        else:
            # Entity does not exist, create it and add to Home Assistant
            _LOGGER.debug(f"No existing tracker found. Creating new tracker for {tracker_key}")
            new_tracker = BoatTracker(tracker_key, "Smart Boat", latitude, longitude)
            domain_data['async_add_entities']([new_tracker])
            domain_data[tracker_key] = new_tracker
            _LOGGER.info(f"Created new tracker entity: {tracker_key}")
    except Exception as e:
        _LOGGER.error(f"Failed to update or create boat location tracker: {str(e)}")
        

def rate_limited_error_log(message):
    """Logs an error message only if the specified time threshold has passed since the last log."""
    global last_error_log_time
    current_time = datetime.now()
    if last_error_log_time is None or current_time - last_error_log_time >= ERROR_LOG_THRESHOLD:
        _LOGGER.warning(message)
        last_error_log_time = current_time

async def update_ha_location(hass: HomeAssistant, latitude_entity: str, longitude_entity: str):
    """Update Home Assistant's location based on sensor data."""
    latitude_state = hass.states.get(latitude_entity)
    longitude_state = hass.states.get(longitude_entity)

    if not latitude_state or not longitude_state:
        rate_limited_error_log("Latitude or longitude entity not found.")
        return

    try:
        latitude = float(latitude_state.state)
        longitude = float(longitude_state.state)
    except ValueError:
        rate_limited_error_log("Invalid latitude or longitude values.")
        return

    # Call the set_location service to update Home Assistant's location
    await hass.services.async_call('homeassistant', 'set_location', {
        'latitude': latitude,
        'longitude': longitude
    })
    _LOGGER.info(f"Home Assistant location updated to Latitude: {latitude}, Longitude: {longitude}")
    
    # Update the boat_location tracker
    await handle_new_location_data(hass, latitude, longitude)


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
        _LOGGER.warning(f"Error deleting zone with ID '{unique_id}': {e}")
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


class BoatTracker(TrackerEntity):
    
    _attr_icon = "mdi:sail-boat"
    
    def __init__(self, identifier, name, initial_latitude=None, initial_longitude=None):
        """Initialize the custom device tracker."""
        self.entity_id = f"device_tracker.{identifier}"  
        self._name = name
        self._latitude = initial_latitude
        self._longitude = initial_longitude
        self._state = None  

        _LOGGER.debug(f"Initializing BoatTracker with ID {identifier} name {name} at initial position ({initial_latitude}, {initial_longitude})")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """Return the state of the device tracker."""
        return self._state or 'not_home'
    
    @property
    def latitude(self):
        return self._latitude

    @property
    def longitude(self):
        return self._longitude

    @property
    def source_type(self):
        return SourceType.GPS
    
    @property
    def should_poll(self):
        """Disable polling."""
        return False    


    def update_location(self, latitude, longitude):
        """Update the latitude and longitude of the tracker."""
        _LOGGER.debug(f"Updating location for {self._name} from ({self._latitude}, {self._longitude}) to ({latitude}, {longitude})")
        
        if self._latitude == latitude and self._longitude == longitude:
            _LOGGER.info(f"{self._name} remains at the same location.")
        else:
            self._latitude = latitude
            self._longitude = longitude
            _LOGGER.info(f"{self._name} has moved to a new location.")
            self._state = 'not_home'  
            self.async_write_ha_state()
