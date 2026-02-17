import logging
from homeassistant.components.lock import LockEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]
    devices = await hass.async_add_executor_job(api.get_devices)

    async_add_entities([PhilipsHomeAccessLock(api, device) for device in devices], update_before_add=True)

class PhilipsHomeAccessLock(LockEntity):
    _attr_should_poll = True
    _attr_scan_interval = timedelta(minutes=1)
    _attr_icon = "mdi:lock-smart"
    def __init__(self, api, device_data):
        self._skip_poll_until = None
        self._api = api
        self._esn = device_data["wifiSN"]

        self._attr_name = device_data.get("lockNickname", "Lock")
        self._attr_unique_id = f"philips_{self._esn}_lock"
        self._attr_is_locked = None
        self._attr_available = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._esn)},
            name=self._attr_name,
            manufacturer="Philips",
            model=device_data.get("productModel", "Lock"),
            sw_version=device_data.get("lockSoftwareVersion"),
        )

    async def async_lock(self, **kwargs):
        self._skip_poll_until = datetime.utcnow() + timedelta(seconds=30)
        resp = await self.hass.async_add_executor_job(self._api.set_lock_state, self._esn, True)
        _LOGGER.warning(
            "Lock API response (%s): %s",
            "lock" if True else "unlock",
            resp
        )

        if isinstance(resp, dict) and resp.get("code") == 200:
            self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        self._skip_poll_until = datetime.utcnow() + timedelta(seconds=30)
        resp = await self.hass.async_add_executor_job(self._api.set_lock_state, self._esn, False)
        _LOGGER.warning(
            "Lock API response (%s): %s",
            "lock" if True else "unlock",
            resp
        )

        if isinstance(resp, dict) and resp.get("code") == 200:
            self._attr_is_locked = False
        self.async_write_ha_state()

    async def async_update(self):
        if self._skip_poll_until and datetime.utcnow() < self._skip_poll_until:
            return
        try:
            devices = await self.hass.async_add_executor_job(self._api.get_devices)
            self._attr_available = True
            for device in devices:
                if device.get("wifiSN") == self._esn:
                    self._attr_is_locked = (device.get("openStatus") == 1)
                    return
        except Exception as err:
            _LOGGER.exception("Update failed: %s", err)
            self._attr_available = False
