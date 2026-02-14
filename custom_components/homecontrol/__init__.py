"""The HomeControl integration."""

from __future__ import annotations
from dataclasses import dataclass

from HomeControlIntegration.custom_components.homecontrol.const import ERROR_VIEW_REGISTRATION_FAILED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .http import async_register_views_once


@dataclass
class HomeControlRuntimeData:
    """Class to hold HomeControl runtime data."""

    # Add runtime data attributes here as needed


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeControl from a config entry."""
    try:
        async_register_views_once(hass)
    except Exception as err:
        raise ConfigEntryError(ERROR_VIEW_REGISTRATION_FAILED) from err

    entry.runtime_data = HomeControlRuntimeData()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
