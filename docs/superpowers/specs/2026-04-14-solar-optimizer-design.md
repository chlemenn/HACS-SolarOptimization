# Solar Optimizer — Design Spec
**Date:** 2026-04-14

## Overview

A Home Assistant custom integration (`solar_optimizer`) that maximizes self-consumption of solar energy by intelligently controlling hot water heating, car charging, and battery storage. A companion custom Lovelace card provides live status and manual overrides.

---

## Priority Order

When surplus solar is available, loads are activated in this order:

1. Hot water heater (target: 8 kWh/day)
2. Car charging (when car is plugged in)
3. Battery storage (via Huawei LUNA / huawei_solar)
4. Grid export (automatic, no action required)

---

## File Structure

```
custom_components/solar_optimizer/
├── __init__.py          # Integration setup, config entry load/unload
├── manifest.json        # Integration metadata, dependencies
├── config_flow.py       # UI-based config and options flow (4 steps)
├── coordinator.py       # DataUpdateCoordinator — 60s polling cycle
├── optimizer.py         # Pure optimization logic (no HA dependencies)
├── sensor.py            # Diagnostic sensors
├── switch.py            # Override and dry-run switches
└── const.py             # Constants and defaults

www/solar-optimizer-card/
└── solar-optimizer-card.js   # Custom Lovelace card (vanilla JS, no build step)
```

---

## Data Flow

1. **Coordinator** polls every 60 seconds:
   - Solar production (user-configured entity)
   - Home consumption (user-configured entity)
   - Battery SOC (from `huawei_solar`)
   - Car plugged-in state (user-configured entity)
   - Hot water thermal safety sensor (user-configured entity)
   - Hot water power consumption (user-configured smart plug entity)

2. **forecast.solar API** called every 30 minutes → today's production curve in kWh

3. **`optimizer.py`** receives a snapshot of all sensor values and returns a list of actions (switch on/off, battery SOC limits)

4. **Coordinator** executes actions via HA service calls, then updates entity states

5. **Lovelace card** reads integration entities for live display

---

## Optimization Logic

### Surplus Calculation
```
surplus_w = solar_production_w - home_consumption_w
```

### Decision Cycle (runs every 60s)

**Step 1 — Hot Water**
- Condition: `surplus_w >= hot_water_min_surplus` AND `hot_water_kwh_today < 8.0` AND `water_temp < thermal_safety_max`
- Action: turn on hot water switch
- Energy tracking: integrate `hot_water_power_sensor` (real watts from smart plug) over time → `hot_water_kwh_today`, reset at midnight
- When hot water switch is on, subtract its live power reading from surplus before evaluating the next step

**Step 2 — Car Charging**
- Condition: car plugged-in entity is `True` AND `(surplus_w - hot_water_power_w) >= car_min_surplus`
- Action: turn on car charger switch
- Note: basic smart switch only — on/off, no power level control

**Step 3 — Battery**
- Not directly activated; Huawei LUNA manages its own charge/discharge
- Coordinator sets battery min/max SOC via `huawei_solar` services (range: 10–95%)
- If surplus remains after steps 1–2, battery charges automatically up to 95%

**Step 4 — Grid Export**
- Anything left exports to grid automatically; no action taken

### Forecast-Based Pre-Heating
- Trigger: forecast.solar predicts < `forecast_preheat_threshold` kWh for today AND current time < `preheat_deadline` AND `hot_water_kwh_today < 8.0`
- Action: turn on hot water switch regardless of surplus to meet daily 8 kWh target before peak tariff hours
- Uses grid or battery power if solar is insufficient

---

## Entities Created by the Integration

| Entity | Type | Description |
|--------|------|-------------|
| `switch.solar_optimizer_force_hot_water` | Switch | Override: run hot water regardless of surplus |
| `switch.solar_optimizer_force_car_charge` | Switch | Override: run car charger regardless of surplus |
| `switch.solar_optimizer_dry_run` | Switch | Log decisions without toggling any switches |
| `sensor.solar_optimizer_surplus_power` | Sensor (W) | Current calculated surplus power |
| `sensor.solar_optimizer_mode` | Sensor | Current state: idle / heating / charging / storing / preheat / error |
| `sensor.solar_optimizer_hot_water_kwh_today` | Sensor (kWh) | Energy delivered to hot water today |
| `sensor.solar_optimizer_forecast_today` | Sensor (kWh) | Forecast.solar predicted production for today |

---

## Configuration Flow (HA UI)

Configured via Settings → Integrations → Add → Solar Optimizer.

**Step 1 — Forecast API**
- forecast.solar API key (optional; free tier uses lat/lon)
- Latitude, longitude, panel tilt (°), azimuth (°), installed capacity (kWp)

**Step 2 — Sensors**
- Solar production entity
- Home consumption entity
- Battery SOC entity (huawei_solar)
- Hot water thermal safety sensor entity
- Hot water power consumption entity (smart plug)
- Car plugged-in entity

**Step 3 — Switches**
- Hot water switch entity
- Car charger switch entity

**Step 4 — Thresholds**

| Parameter | Default | Description |
|-----------|---------|-------------|
| Hot water daily target | 8.0 kWh | Energy to deliver per day |
| Thermal safety max | 65 °C | Stop heating above this temperature |
| Hot water min surplus | 500 W | Minimum surplus before activating hot water |
| Car charge min surplus | 1400 W | Minimum surplus before activating car charger |
| Battery min SOC | 10 % | Never discharge below this |
| Battery max SOC | 95 % | Never charge above this |
| Forecast pre-heat threshold | 4.0 kWh | Trigger grid/battery top-up if day forecast is below this |
| Pre-heat deadline | 10:00 | Stop pre-heating after this time |

All thresholds are re-configurable later via the card's **Configure** button (HA options flow).

---

## Lovelace Card (Layout A — Status Dashboard)

**Card type:** `solar-optimizer-card` (registered in `www/solar-optimizer-card/solar-optimizer-card.js`)

**Layout:**
```
┌─────────────────────────────────────┐
│ ☀ Solar Optimizer        ● HEATING  │
├──────────────┬──────────┬───────────┤
│  3.2 kW      │ 1.4 kW   │  1.8 kW  │
│  SOLAR       │ HOME     │  SURPLUS  │
├─────────────────────────────────────┤
│ 🔥 Hot Water            5.2 / 8 kWh │
│ ████████████░░░░░░░░░░░░            │
├──────────────────┬──────────────────┤
│  🚗 Car  OFF     │  🔋 Battery  72% │
├──────────────────┴──────────────────┤
│  [Force Hot Water]  [Force Car]     │
│                     [Configure ⚙]  │
└─────────────────────────────────────┘
```

**Card config (in Lovelace YAML):**
```yaml
type: custom:solar-optimizer-card
entity: sensor.solar_optimizer_mode   # integration entry point
```
No further manual YAML needed — all entity mappings come from the integration config.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| forecast.solar API unavailable | Log warning, use last cached forecast (up to 24h). Fall back to real-time surplus only. |
| Sensor entity unavailable | Skip optimization cycle for that turn, set mode to `error` |
| Switch fails to toggle | Retry once after 10s, then log and continue — never block the main loop |
| Invalid config entities | Caught at setup time with clear user-facing error messages in config flow |

---

## Testing

- **Unit tests** (`tests/test_optimizer.py`): pure logic tests for `optimizer.py` with mocked sensor snapshots — no HA dependencies
- **Integration tests**: using `pytest-homeassistant-custom-component` for coordinator, config flow, and entity behavior
- **Dry-run mode**: `switch.solar_optimizer_dry_run` — optimizer runs and logs all decisions without toggling any physical switches
