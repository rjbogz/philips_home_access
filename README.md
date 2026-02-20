# Philips Home Access (Home Assistant Integration)

Home Assistant custom integration for Philips Home Access WiFi locks.

This integration allows you to monitor and control Philips Home Access locks directly from Home Assistant.

## Features

- Lock and unlock your Philips Home Access lock
- View lock status
- Monitor battery level
- Monitor WiFi signal strength
- Automatic session expiration detection
- Repair flow support for re-authentication

## Supported Devices

So far, I have only tested with:

- Philips Home Access WiFi Locks

Other Philips locks using a direct wifi connection may also work. Let me know if your lock works or help me add support it.

## Notes

- You can not be logged in to the Philips Home Access app and this integration at the same time. Logging in to one will sign you out of the other.
- I have only added basic sensors for this, but I'm open to adding more support (getting other data about the lock, adjusting settings, etc.)
- This integration is a work in progress. I only have 1 lock so my testing was limited.

## Installation

### Option 1: Install via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three-dot menu → **Custom repositories**
4. Add this repository: https://github.com/rjbogz/philips_home_access
5. Select category: **Integration**
6. Click **Install**
7. Restart Home Assistant

---

### Option 2: Manual installation

1. Copy the folder: custom_components/philips_home_access
2. Restart Home Assistant

---

## Configuration

1. Go to: Settings → Devices & Services → Add Integration
2. Search for: Philips Home Access
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

---

## Known Limitations

- Requires Philips cloud access
- Polling interval: 60 seconds
- Internet connection required

---

## Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.philips_home_access: debug```

## Support

If this integration helped you, consider supporting development:

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png)](https://buymeacoffee.com/rjbogz)