# Heidelberg Energy Control for Home Assistant
This integration allows you to monitor and control your **Heidelberg Energy Control** wallbox in Home Assistant via Modbus TCP.


## Overview
The Heidelberg Energy Control wallbox supports the Modbus RTU protocol for external control. Since Home Assistant communicates over your network, a **Modbus TCP to RTU gateway** (like a PE11 or similar) is typically required to bridge the connection unless your wallbox is equipped with a native network interface.


## Installation via HACS
Since this integration is not yet part of the HACS default store, you need to add it as a **Custom Repository**:

1. In Home Assistant, navigate to **HACS**.
2. Click on **Integrations**.
3. Click the **three dots** in the upper right corner and select **Custom repositories**.
4. Enter the URL of this GitHub project:
`https://github.com/Schrolli91/heidelberg_energy_control`
5. Select **Integration** as the category.
6. Click **Add**.
7. The integration will now appear in your list. Click **Download** and choose the latest version.
8. **Restart Home Assistant.**


## Configuration
Once restarted, you can set up the integration through the UI:

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Heidelberg Energy Control**.
4. Enter the required details:
* **Host**: The IP address of your Modbus TCP gateway.
* **Port**: Usually `502`.
* **Slave ID**: The Modbus ID of your wallbox (default is often `1`).


### Features
This integration provides a comprehensive set of entities to monitor and control your wallbox:

#### 🎮 Controls
* **Charge Enable**: Toggle to start or stop the charging process.
* **Charging Current Limit**: Adjust the maximum allowed charging current (6A - 16A).

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
* **Charge Status Code**: Raw status code from the wallbox (e.g., State A, B, C).
* **Internal Temperature**: Monitor the housing temperature of the wallbox.
* **Energy since Power On**: Energy consumed since the last reboot of the device.

#### 🏠 Local Control
* **No Cloud Required**: Works completely offline via your local network.
* **Fast Updates**: Direct communication via Modbus TCP for near real-time data.


## Disclaimer
**This is a private, community-driven project. It is NOT an official integration from Heidelberg (Amperfied).**
The author(s) of this integration are not responsible for any damage to your hardware, wallbox, vehicle, or electrical system. Use this integration at your own risk.

* Modbus communication directly influences the charging behavior; ensure your gateway and network are stable.
* Always follow the official manual provided by Heidelberg for wiring and safety instructions.