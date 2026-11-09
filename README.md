[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Schrolli91/heidelberg_energy_control?style=flat-square)](https://github.com/Schrolli91/heidelberg_energy_control/releases)
[![License](https://img.shields.io/github/license/Schrolli91/heidelberg_energy_control?style=flat-square)](https://github.com/Schrolli91/heidelberg_energy_control/blob/main/LICENSE)
[![Maintenance](https://img.shields.io/badge/maintained-yes-brightgreen.svg)](https://github.com/Schrolli91/heidelberg_energy_control/graphs/commit-activity)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Schrolli91/heidelberg_energy_control?style=flat-square)](https://github.com/Schrolli91/heidelberg_energy_control/commits/main)

# Heidelberg/Amperfied Integration for Home Assistant

![Heidelberg](https://github.com/Schrolli91/heidelberg_energy_control/blob/main/banner.png?raw=true)

This integration allows you to monitor and control your **Heidelberg/Amperfied** wallbox in Home Assistant via Modbus TCP.

## Overview
The Heidelberg Energy Control wallbox supports the Modbus RTU protocol for external control. Since Home Assistant communicates over your network, a **Modbus TCP to RTU gateway** (like a PE11 or similar) is typically required to bridge the connection unless your wallbox is equipped with a native network interface.

### Heidelberg/Amperfied Connect Series
This integration also supports the **Heidelberg Connect series** (heidelberg.home and heidelberg.solar). These wallboxes feature a native network interface and support Modbus TCP directly, eliminating the need for an external gateway.

**Note:** Support for the Connect series is currently in **beta stage**.

If you encounter any problems or have suggestions for improvements, please report them on our [Issues page](https://github.com/Schrolli91/heidelberg_energy_control/issues).

Fully compatible with the evcc home assistant charger.

### Other Wallboxes
The integration also supports other wallboxes which will follow the Heidelberg Modbus Layout.
These wallboxes are:
- tbd

## Installation via HACS
Requires Home Assistant **2026.9.0** or newer.

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
* **Standby Mode**: Enable or disable the wallbox power-saving standby function (requires firmware ≥ 1.0.8).
* **Watchdog & FailSafe**: Configure the wallbox's built-in safety net for Home Assistant comms loss — Watchdog Timeout (s; 0 disables) and FailSafe Current (A) that takes over if HA stops polling. Requires firmware ≥ 1.0.8.
* **Maximal Power Target**: Set a power ceiling in Watts (0 disables) and let the wallbox choose 1-phase or 3-phase operation by itself — the automatic phase switch. Requires a connect.solar / connect.solar pro wallbox with firmware ≥ 2.0.2. **Read the note below before using it.**

> ### ⚠️ Choose one control method — current *or* power
>
> This integration gives you two independent ways to limit charging, and it is up to you to pick one:
>
> * **Charging Current Limit** (Modbus register 261) — you set the amps, and you choose the number of phases yourself.
> * **Maximal Power Target** (Modbus register 500) — you set the watts, and the wallbox decides 1-phase or 3-phase on its own.
>
> Amperfied's register specification states that these two are **mutually exclusive**. This integration deliberately does *not* enforce that, so you are free to use whichever suits your setup — but driving both at the same time hands the wallbox two conflicting ceilings, and which one wins is undefined.
>
> * **To use the power target:** set the Watts you want, and leave the Charging Current Limit at its maximum.
> * **To use the current limit:** leave the Maximal Power Target at `0`, which disables it.
>
> **Charge Enable always works.** It stops the charge by writing `0` to register 261, and that takes effect whether or not a power target is set — you can always stop charging from Home Assistant. What is undefined is the case where both limits are *active* at the same time: a current limit and a power target can contradict each other, and the specification does not say which one the wallbox will follow.

#### 📊 Monitoring (Sensors)
* **Charging Power**: Real-time power consumption in Watts.
* **Energy Session**: Energy consumed during the current or last charging session (kWh).
* **Energy Total**: Energy consumed since the wallbox installed (kWh).
* **Energy Since Power On**: Energy consumed since the wallbox was powered on (kWh).
* **Vehicle Status**: Shows the current state of the vehicle (e.g., Standby, Charging).
* **Vehicle Connection**: Indicates if a vehicle is plugged into the wallbox.
* **Phases Active**: Number of active phases (1-3).
* **Target Current**: Currently set target current on the wallbox (A).

#### 🔍 Diagnostics & Advanced Data
* **Total Energy**: Lifetime energy consumption of the wallbox.
* **Phase-specific Data**: Individual monitoring of Voltage (V) and Current (A) for each phase (**L1, L2, L3**).
* **Hardware Limit (Min and Max)**: Displays the physical current limit, set via modbus on the wallbox.
* **External Lock**: Status of the hardware lock contact.
* **Internal Temperature**: Monitor the housing temperature of the wallbox.
* **Maximal Power Set**: Reads back the power target currently stored in the wallbox (W).

#### 🏠 Local Control
* **No Cloud Required**: Works completely offline via your local network.
* **Fast Updates**: Direct communication via Modbus TCP for near real-time data (Configurable update interval).
* **EVCC Compatible**: Integrates seamless with the evcc home assitant charger.

## Disclaimer
**This is a private, community-driven project. It is NOT an official integration from Heidelberg (Amperfied).**
The author(s) of this integration are not responsible for any damage to your hardware, wallbox, vehicle, or electrical system. Use this integration at your own risk.

* Modbus communication directly influences the charging behavior; ensure your gateway and network are stable.
* Always follow the official manual provided by Heidelberg for wiring and safety instructions.

## Removal
To remove the integration:

1. Go to **Settings** > **Devices & Services**.
2. Find the **Heidelberg Energy Control** entry.
3. Click the three-dot menu and select **Delete**.
4. Confirm the deletion.
5. Restart Home Assistant.
