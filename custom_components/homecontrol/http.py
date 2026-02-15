from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from .helpers import async_get_dashboards

from .const import DOMAIN, CONF_DASHBOARD


def _get_entry(hass: HomeAssistant):
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _get_dashboard(hass: HomeAssistant) -> str | None:
    """Return the selected dashboard id (url_path) or None.

    Normalise possible stored shapes: single string, list/set of strings, or missing.
    """
    entry = _get_entry(hass)
    if not entry:
        return None

    val = entry.options.get(CONF_DASHBOARD)
    if val is None:
        return None
    # If option stored as iterable (list/set/tuple), pick the first element
    if isinstance(val, (list, set, tuple)):
        try:
            return str(next(iter(val)))
        except StopIteration:
            return None
    return str(val)


class HomeControlDashboardView(HomeAssistantView):
    url = "/api/homecontrol/dashboard"
    name = "api:homecontrol:dashboard"
    requires_auth = True

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]

        dashboards = await async_get_dashboards(hass)
        dashboard_id = _get_dashboard(hass)

        conf = dashboards.get(dashboard_id) if dashboard_id else None
        if not conf:
            return self.json({"error": "dashboard_not_found"}, status_code=404)

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
            url_path = getattr(conf, "url_path", None) or getattr(conf, "path", None)

        key_str = str(url_path or dashboard_id)
        label = title or url_path or key_str

        payload = {
            "dashboard_id": dashboard_id,
            "dashboard_title": label,
            "generated_at": dt_util.utcnow().isoformat(),
            "views": dashboards.get(str(dashboard_id), []),
        }
        return self.json(payload)


def async_register_views_once(hass: HomeAssistant) -> None:
    """Register HTTP views exactly once."""
    hass.data.setdefault(DOMAIN, {})

    if hass.data[DOMAIN].get("_http_registered"):
        return

    hass.http.register_view(HomeControlDashboardView())
    hass.data[DOMAIN]["_http_registered"] = True
