# Version Dependency Analysis: Heidelberg Energy Control Integration

## Executive Summary

The analysis of all entities and the API class reveals **excellent version management** with minimal dependencies. There are **no critical cross-dependencies** that cannot be resolved.

## Version Overview

### Version 1.0.0 (Base Version)
- **Sensors**: Charging State, Current (Total + L1/L2/L3), Voltage (L1/L2/L3), PCB Temperature, Phases Active
- **Binary Sensors**: External Lock State, Is Plugged, Is Charging
- **API**: Reads all registers, but some values may be 0 on older firmware

### Version 1.0.4
- **Sensors**: Charging Power, Energy Since Power On
- **Switches**: Remote Lock Command

### Version 1.0.7 (Virtual Logic)
- **Sensors**: Total Energy, Session Energy, Command Target Current
- **Number**: Virtual Target Current
- **Switch**: Virtual Enable
- **Coordinator**: Virtual Logic (Bidirectional Sync)

## Dependency Analysis

### ✅ Clean Dependencies

#### 1. **Session Energy (1.0.7) → Total Energy (1.0.7)**
```python
# sensor.py line 91: min_version="1.0.7" # depends on TOTAL_ENERGY
# heidelberg_sensor_energy_session.py line 38: raw_total = data.get(DATA_TOTAL_ENERGY)
```
- **Status**: ✅ Clean
- **Reason**: Both have the same minimum version (1.0.7). Session Energy needs Total Energy as raw data source, but both become available simultaneously.

#### 2. **Virtual Logic (1.0.7) → Command Target Current (1.0.7)**
```python
# coordinator.py line 53: self.supports_virtual_logic = self.is_supported("1.0.7", ...)
# coordinator.py line 80: hw_current = float(data.get(COMMAND_TARGET_CURRENT, 0.0))
```
- **Status**: ✅ Clean
- **Reason**: Coordinator explicitly checks for 1.0.7 and uses COMMAND_TARGET_CURRENT only if available.

#### 3. **Virtual Entities (1.0.7) → Coordinator Virtual Logic**
```python
# number.py line 44: min_version="1.0.7" # depends on COMMAND_TARGET_CURRENT
# switch.py line 47: min_version="1.0.7" # depends on COMMAND_TARGET_CURRENT
```
- **Status**: ✅ Clean
- **Reason**: All virtual entities have the same minimum version. Coordinator implements fallback logic.

#### 4. **Phases Active (1.0.0) → Current L1/L2/L3 (1.0.0)**
```python
# sensor.py line 184: min_version="1.0.0" # depends on single phase currents
# api.py line 183: active_phases = sum(1 for i in [curr_l1, curr_l2, curr_l3] if i > 0.1)
```
- **Status**: ✅ Clean
- **Reason**: All have the same minimum version 1.0.0.

### ⚠️ Potential Issues (But With Solutions)

#### 1. **Charging Power (1.0.4) → API Register 9**
```python
# sensor.py line 72: min_version="1.0.4"
# api.py line 199: DATA_CHARGING_POWER: data_regs[9],
```
- **Status**: ⚠️ Potential issue, but **caught**
- **Analysis**:
  - On firmware < 1.0.4, register 9 may be 0 or undefined
  - Coordinator.is_supported() prevents sensor creation
  - API still returns value (possibly 0), but sensor is never instantiated
- **Assessment**: ✅ No problem - version check prevents usage

#### 2. **Energy Since Power On (1.0.4) → API Register 10-11 (32-bit)**
```python
# sensor.py line 102: min_version="1.0.4"
# api.py line 200: DATA_ENERGY_SINCE_POWER_ON: self._to_32bit(data_regs, 10) / 1000.0,
```
- **Status**: ⚠️ Potential issue, but **caught**
- **Analysis**:
  - _to_32bit() has IndexError protection (lines 219-221)
  - On incomplete registers, returns 0
  - Version check prevents creation on old firmware
- **Assessment**: ✅ No problem

#### 3. **Total Energy (1.0.7) → API Register 12-13 (32-bit)**
```python
# sensor.py line 82: min_version="1.0.7"
# api.py line 201: DATA_TOTAL_ENERGY: self._to_32bit(data_regs, 12) / 1000.0,
```
- **Status**: ⚠️ Potential issue, but **caught**
- **Analysis**:
  - Same protection mechanism as above
  - Coordinator explicitly checks for 1.0.7
- **Assessment**: ✅ No problem

### ✅ Safe Dependencies

#### 4. **Is Plugged/Is Charging (1.0.0) → Charging State (1.0.0)**
```python
# binary_sensor.py line 40: min_version="1.0.0" # depends on chargingstate sensor
# api.py line 205-206: DATA_IS_PLUGGED: data_regs[0] >= 4, DATA_IS_CHARGING: data_regs[9] > 0,
```
- **Status**: ✅ Safe
- **Reason**: All based on base registers (0 and 9) available in 1.0.0.

## API Class Analysis

### HeidelbergEnergyControlAPI
```python
# api.py line 223-229: _register_to_version()
# api.py line 216-221: _to_32bit() with IndexError protection
```

**Strengths:**
- Robust version detection
- Fault-tolerant 32-bit register combination
- All register limits are checked

**Weaknesses:**
- No explicit register existence check per version
- Returns values even on incomplete registers (but with defaults)

## Coordinator as Central Version Manager

```python
# coordinator.py line 173-204: is_supported()
# coordinator.py line 51-53: supports_virtual_logic check
# coordinator.py line 76-77: Fallback for old firmware
# coordinator.py line 117-119: Write protection for old firmware
```

**Functions:**
1. **Version Check**: Central method `is_supported(min_required, feature_name)`
2. **Fallback Logic**: Virtual logic disabled on old firmware
3. **Write Protection**: Prevents write access to unsupported registers
4. **Informative Logging**: Clear messages on version conflicts

## Conclusion

### ✅ **No Critical Issues**

**All dependencies are cleanly resolved:**

1. **Version Consistency**: Entities with shared dependencies have the same minimum version
2. **Defensive Programming**: API has fallbacks for incomplete registers
3. **Central Control**: Coordinator prevents creation/use of unsupported features
4. **Clear Separation**: Virtual logic (1.0.7) is completely isolated and optional

### Recommendations

1. **Documentation**: Communicate version 1.0.7 as "recommended minimum version"
2. **Testing**: Tests for firmware 1.0.0-1.0.6 (Legacy Mode) and 1.0.7+ (Full Features)
3. **Monitoring**: Keep log messages for version conflicts

**Result**: The version management is **production-ready** and **fault-tolerant**.

---

Report from 15.02.2026 - written by MiMo V2 Flash
