from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .options_flow import OptionsFlowHandler

UNIQUE_ID = "homecontrol_singleton"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()

        # print translation title
        return self.async_create_entry(title="HomeControl Dashboard Publisher", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()
