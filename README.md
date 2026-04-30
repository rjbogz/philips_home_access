# Philips Home Access (Smart Plug)

Home Assistant custom integration for Philips Home Access WiFi locks and compatible Bluetooth-WiFi bridge smart plug control.

This integration allows you to monitor and control Philips Home Access locks directly from Home Assistant, and adds smart plug power control for supported Philips Home Access Bluetooth-WiFi bridges.

This project is a fork of the original [Philips Home Access integration](https://github.com/rjbogz/philips_home_access) by **rjbogz**. Credit and thanks to rjbogz for the original integration foundation.

## Features

- Lock and unlock your Philips Home Access lock
- View lock status
- Monitor battery level
- Monitor WiFi signal strength
- Automatic session expiration detection
- Repair flow support for re-authentication
- Smart plug / bridge power control for supported gateways

## Supported Devices

So far, I have only tested with:

- Philips Home Access WiFi Locks
  - This also includes locks that are controlled through a wifi gateway
- Philips Home Access Bluetooth-WiFi bridge smart plug control
  - Tested with a gateway reporting `deviceType: GATEWAY`, `model: WGAH2`, and `productModel: DDL203`

Let me know if your lock or bridge works, or help me add support for more models.

## Notes

- You can not be logged in to the Philips Home Access app and this integration at the same time. Logging in to one will sign you out of the other.
- Smart plug support depends on the bridge exposing `gwPowerStatus` and accepting the Philips gateway power endpoint.
- This integration is a work in progress. My testing is limited to my own Philips Home Access devices.

## Installation

### Option 1: Install via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three-dot menu → **Custom repositories**
4. Add this repository: https://github.com/HUDMATT/philips_home_access_smart_switch_integration
5. Select category: **Integration**
6. Click **Install**
7. Restart Home Assistant

---

### Option 2: Manual installation

1. Copy the folder: custom_components/philips_home_access_w_smart_plug
2. Restart Home Assistant

---

## Configuration

1. Go to: Settings → Devices & Services → Add Integration
2. Search for: Philips Home Access (Smart Plug)
3. Enter:

- Username (email)
- Password
- Region

4. Click Submit

---

## Authentication Handling

This integration automatically detects when your session becomes invalid.

If you log in through the official Philips app, Home Assistant may require re-authentication. A Repair notification will appear allowing you to enter updated credentials.

---

## Entities Created

For each lock:

- Lock entity
- Battery sensor
- WiFi signal strength sensor
- Auto-Lock toggle
- Auto-Lock delay (10s-180s)


For each gateway:

- WiFi signal strength sensor
- Smart plug / bridge power switch when `gwPowerStatus` is available

---

## Known Limitations

- Requires Philips cloud access
- Polling interval: 60 seconds
- Internet connection required

---

## Debug Logging

Add to `configuration.yaml`:

```
logger:
  logs:
    custom_components.philips_home_access_w_smart_plug: debug
```

## Credits

This fork builds on the original Philips Home Access custom integration by **rjbogz**:

https://github.com/rjbogz/philips_home_access

## Support

If this integration helped you, consider supporting development:

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png)](https://buymeacoffee.com/rjbogz)
