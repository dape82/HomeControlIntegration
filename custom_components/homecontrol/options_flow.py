from __future__ import annotations

from .const import (
    ERROR_NO_DASHBOARDS,
)
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
import voluptuous as vol
import pprint
import traceback
import logging

from homeassistant import config_entries

from .const import CONF_DASHBOARD
from .helpers import async_get_dashboards


_LOGGER = logging.getLogger(__name__)


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        configs = await async_get_dashboards(self.hass)

        # Guard: async_get_dashboards may return None -> abort if no dashboards
        if not configs:
            _LOGGER.debug("No dashboards returned from async_get_dashboards")
            return self.async_abort(reason=ERROR_NO_DASHBOARDS)

        # Build selection options from collected configs (only storage dashboards expected here)
        dashboard_options: dict[str, str] = {}
        for key, conf in configs.items():
            # conf can be a dict or object; handle dict first
            title = None
            url_path = None
            if isinstance(conf, dict):
                title = conf.get("title") or (conf.get("config") or {}).get("title")
                url_path = (
                    conf.get("url_path")
                    or conf.get("path")
                    or (conf.get("config") or {}).get("url_path")
                )
            else:
                title = getattr(conf, "title", None)
                url_path = getattr(conf, "url_path", None) or getattr(
                    conf, "path", None
                )

            key_str = str(url_path or key)
            label = title or url_path or key_str
            dashboard_options[key_str] = label

        # Prepare single-select: show label (title) but store url_path (keys in dashboard_options)
        # voluptuous_serialize supports dict validators to render labels in the UI:
        # pass a mapping of value -> label so the UI shows the title but stores the url_path
        choices_map = dict(dashboard_options)  # { url_path: title }
        choices = list(choices_map.keys())

        # Normalize default: previously stored option might be list -> pick first
        stored = self.config_entry.options.get(CONF_DASHBOARD, None)
        if isinstance(stored, list):
            default_choice = stored[0] if stored else None
        else:
            default_choice = stored

        # Validate choices and default
        if not choices:
            # Abort the flow if no dashboards available (add translation key "no_dashboards" in strings.json)
            return self.async_abort(reason=ERROR_NO_DASHBOARDS)
        if default_choice not in choices:
            default_choice = choices[0]

        # Require the user to choose exactly one dashboard (store the url_path).
        # Use the dict validator so the UI shows labels (titles) while values are the url_path keys.
        # Use the option key (CONF_DASHBOARD) as field name so strings.json provides the label
        schema = vol.Schema(
            {
                vol.Required(CONF_DASHBOARD, default=default_choice): vol.In(
                    choices_map
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
