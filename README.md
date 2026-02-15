[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Schrolli91/heidelberg_energy_control?style=flat-square)](https://github.com/Schrolli91/heidelberg_energy_control/releases)
[![License](https://img.shields.io/github/license/Schrolli91/heidelberg_energy_control?style=flat-square)](LICENSE)
[![Maintenance](https://img.shields.io/badge/maintained-yes-brightgreen.svg)](https://github.com/Schrolli91/heidelberg_energy_control/graphs/commit-activity)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Schrolli91/heidelberg_energy_control?style=flat-square)](https://github.com/Schrolli91/heidelberg_energy_control/commits/main)

# Heidelberg Energy Control for Home Assistant

![Heidelberg](banner.png)

This integration allows you to monitor and control your **Heidelberg Energy Control** wallbox in Home Assistant via Modbus TCP.

## Overview
The Heidelberg Energy Control wallbox supports the Modbus RTU protocol for external control. Since Home Assistant communicates over your network, a **Modbus TCP to RTU gateway** (like a PE11 or similar) is typically required to bridge the connection unless your wallbox is equipped with a native network interface.

Fully compatible with the evcc home assitant charger.

## Installation via HACS
This integration is part of the **HACS Default Store**. To install it:

1. In Home Assistant, navigate to **HACS**.
2. Search for **Heidelberg Energy Control**.
3. Click **Download** and choose the latest version.
4. **Restart Home Assistant.**

## Configuration
Once restarted, you can set up the integration through the UI:

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Heidelberg Energy Control**.
4. Enter the required details:
    * **Display Name**: A name for your wallbox (e.g., "Garage Wallbox").
    * **Host**: The IP address of your Modbus TCP gateway.
    * **Port**: Usually `502`.
    * **Slave ID**: The Modbus ID of your wallbox (default is often `1`).

### Options (Dynamic Configuration)
After the initial setup, you can adjust settings without restarting:
1. Go to **Settings** > **Devices & Services**.
2. Find the **Heidelberg Energy Control** entry.
3. Click **Configure**.
4. **Polling Interval**: Adjust how often data is requested (between 3 and 30 seconds / Defaults to 10 seconds).

## Features
This integration provides a comprehensive set of entities to monitor and control your wallbox:

#### 🎮 Controls
* **Charge Enable**: Toggle to start or stop the charging process.
* **Charging Current Limit**: Adjust the maximum allowed charging current (6A - 16A).
* **Remote Lock**: Disable and lock the charging process to prevent unauthorized use.

#### 📊 Monitoring (Sensors)
* **Charging Power**: Real-time power consumption in Watts.
* **Energy Session**: Energy consumed during the current or last charging session (kWh).
* **Vehicle Status**: Shows the current state of the vehicle (e.g., Standby, Charging).
* **Vehicle Connection**: Indicates if a vehicle is plugged into the wallbox.

#### 🔍 Diagnostics & Advanced Data
* **Total Energy**: Lifetime energy consumption of the wallbox.
* **Phase-specific Data**: Individual monitoring of Voltage (V) and Current (A) for each phase (**L1, L2, L3**).
* **Hardware Limit**: Displays the physical current limit, set via modbus on the wallbox.
* **External Lock**: Status of the hardware lock contact.
* **Internal Temperature**: Monitor the housing temperature of the wallbox.
* **Modbus Performance**: Diagnostic logs show the response time of your gateway (useful for optimizing PV-surplus charging like **evcc**).

#### 🏠 Local Control
* **No Cloud Required**: Works completely offline via your local network.
* **Fast Updates**: Direct communication via Modbus TCP for near real-time data.
* **EVCC Compatible**: Integrates seamless with the evcc home assitant charger.

## Disclaimer
**This is a private, community-driven project. It is NOT an official integration from Heidelberg (Amperfied).**
The author(s) of this integration are not responsible for any damage to your hardware, wallbox, vehicle, or electrical system. Use this integration at your own risk.

* Modbus communication directly influences the charging behavior; ensure your gateway and network are stable.
* Always follow the official manual provided by Heidelberg for wiring and safety instructions.