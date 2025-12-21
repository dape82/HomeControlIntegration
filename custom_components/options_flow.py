from __future__ import annotations

from homeassistant import config_entries


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_abort(reason="no_options")
