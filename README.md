# Heidelberg Energy Control for Home Assistant

This integration allows you to monitor and control your **Heidelberg Energy Control** wallbox in Home Assistant via Modbus TCP.

## Installation via HACS

Since this integration is not yet part of the HACS default store, you need to add it as a **Custom Repository**:

1. In Home Assistant, navigate to **HACS**.
2. Click on **Integrations**.
3. Click the **three dots** in the upper right corner and select **Custom repositories**.
4. Enter the URL of this GitHub project:
`https://github.com/Schrolli91/heidelberg_energy_control`
5. Select **Integration** as the category.
6. Click **Add**.
7. The integration will now appear in your list. Click **Download** and choose the latest version (e.g., `0.9.0`).
8. **Restart Home Assistant.**

## Configuration

Once restarted, you can set up the integration through the UI:

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Heidelberg Energy Control**.
4. Follow the configuration steps (enter the IP address, Port, and Modbus ID of your wallbox).

## Features

* **Real-time Monitoring**: Track charging current, power consumption, and status.
* **Charging Control**: Start/Stop charging and adjust the maximum charging current.
* **Local Control**: Works completely offline via Modbus TCP.