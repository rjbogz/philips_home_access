from __future__ import annotations
from datetime import timedelta
import logging
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]

    devices = await hass.async_add_executor_job(api.get_devices)
    _LOGGER.debug("sensor: get_devices returned %d devices", len(devices))

    if not devices:
        _LOGGER.warning("sensor: no devices returned; no sensors will be created")
        return

    entities = []
    for d in devices:
        esn = d.get("wifiSN")
        if not esn:
            _LOGGER.debug("sensor: skipping device without wifiSN: %s", d)
            continue

        name = d.get("lockNickname") or "Philips Home Access Lock"

        # Use dict for device_info (HA-native)
        device_info = {
            "identifiers": {(DOMAIN, esn)},
            "name": name,
            "manufacturer": "Philips",
            "model": d.get("productModel", "Philips Home Access Lock"),
            "sw_version": d.get("lockSoftwareVersion"),
        }

        entities.append(PhilipsBatterySensor(api, esn, name, device_info))
        entities.append(PhilipsSignalSensor(api, esn, name, device_info))

    _LOGGER.debug("sensor: adding %d entities", len(entities))
    async_add_entities(entities, update_before_add=True)


class PhilipsBaseSensor(SensorEntity):
    _attr_should_poll = True
    _attr_scan_interval = timedelta(minutes=1)
    def __init__(self, api, esn: str, name: str, device_info: dict):
        self._api = api
        self._esn = esn
        self._name = name
        self._attr_device_info = device_info
        self._attr_available = True

    async def async_update(self):
        try:
            devices = await self.hass.async_add_executor_job(self._api.get_devices)
            for d in devices:
                if d.get("wifiSN") == self._esn:
                    self._attr_available = True
                    self._handle_device(d)
                    return
            self._attr_available = False
        except Exception as err:
            _LOGGER.debug("sensor: update failed for %s: %r", self._esn, err)
            self._attr_available = False

    def _handle_device(self, device: dict) -> None:
        raise NotImplementedError


class PhilipsBatterySensor(PhilipsBaseSensor):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery"

    def __init__(self, api, esn: str, name: str, device_info: dict):
        super().__init__(api, esn, name, device_info)
        self._attr_name = f"{name} Battery"
        self._attr_unique_id = f"philips_{esn}_battery"

    def _handle_device(self, d: dict) -> None:
        self._attr_native_value = d.get("power")


class PhilipsSignalSensor(PhilipsBaseSensor):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_icon = "mdi:wifi"

    def __init__(self, api, esn: str, name: str, device_info: dict):
        super().__init__(api, esn, name, device_info)
        self._attr_name = f"{name} WiFi Signal"
        self._attr_unique_id = f"philips_{esn}_rssi"

    def _handle_device(self, d: dict) -> None:
        raw = d.get("rssi", 0)
        if isinstance(raw, str):
            raw = raw.replace("dBm", "").strip()
        try:
            self._attr_native_value = float(raw)
        except Exception:
            self._attr_native_value = None
