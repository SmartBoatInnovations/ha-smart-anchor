import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .zone_management import create_zone, delete_zone, setup_periodic_location_updates
from homeassistant.helpers import entity_registry as er

DOMAIN = "smart_anchor"
_LOGGER = logging.getLogger(__name__)

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



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    
    _LOGGER.debug("In async_setup_entry.")

    setup_or_update_config(hass, entry)
    
    entry.async_on_unload(entry.add_update_listener(update_listener))
       
    hass.data[DOMAIN]['ha_location_cancellation'] = await setup_periodic_location_updates(
        hass, 
        hass.data[DOMAIN]["latitude_entity"], 
        hass.data[DOMAIN]["longitude_entity"]
    )

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
