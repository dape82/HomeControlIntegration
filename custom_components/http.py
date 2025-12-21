from __future__ import annotations

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN


class HomeControlDashboardView(HomeAssistantView):
    """Return a JSON dashboard snapshot."""

    url = "/api/homecontrol/dashboard"
    name = "api:homecontrol:dashboard"
    requires_auth = True  # nutzt Home Assistant Auth (Bearer Token)

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]

        # Minimal: ein Snapshot aller States (später filtern!)
        states = hass.states.async_all()

        payload = {
            "title": "HomeControl Dashboard",
            "generated_at": dt_util.utcnow().isoformat(),
            "entity_count": len(states),
            "entities": [
                {
                    "entity_id": s.entity_id,
                    "state": s.state,
                    "attributes": dict(s.attributes),
                    "last_changed": s.last_changed.isoformat(),
                }
                for s in states
            ],
        }

        return self.json(payload)


def async_register_views_once(hass: HomeAssistant) -> None:
    """Register HTTP views exactly once."""
    hass.data.setdefault(DOMAIN, {})

    if hass.data[DOMAIN].get("_http_registered"):
        return

    hass.http.register_view(HomeControlDashboardView())
    hass.data[DOMAIN]["_http_registered"] = True
