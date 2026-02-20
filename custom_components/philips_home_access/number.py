from homeassistant.components.number import NumberEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]
    devices = await hass.async_add_executor_job(api.get_devices)
    async_add_entities([PhilipsAutoLockTime(api, d) for d in devices])
    hass.data[DOMAIN].setdefault("autolock_enabled", {})
    hass.data[DOMAIN]["autolock_enabled"].setdefault(entry.entry_id, {})

class PhilipsAutoLockTime(NumberEntity):
    _attr_native_min_value = 10
    _attr_native_max_value = 180
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"

    def __init__(self, api, device):
        self._api = api
        self._esn = device["wifiSN"]
        self._attr_name = f"{device['lockNickname']} Auto-Lock Delay"
        self._attr_unique_id = f"{self._esn}_autolock_time"
        self._attr_native_value = device.get("autoLockTime", 30)
        self._attr_available = (device.get("amMode") == 0)
        self._attr_device_info = {"identifiers": {(DOMAIN, self._esn)}}

    @property
    def available(self) -> bool:
        try:
            entry_id = self.platform.config_entry.entry_id
            cached = self.hass.data[DOMAIN]["autolock_enabled"].get(entry_id, {})
            if self._esn in cached:
                return bool(cached[self._esn])
        except Exception:
            pass
        return self._attr_available

    async def async_set_native_value(self, value):
        await self.hass.async_add_executor_job(self._api.set_auto_lock_time, self._esn, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_update(self):
        devices = await self.hass.async_add_executor_job(self._api.get_devices)
        for d in devices:
            if d["wifiSN"] == self._esn:
                self._attr_native_value = d.get("autoLockTime")
                self._attr_available = (d.get("amMode") == 0)
                break