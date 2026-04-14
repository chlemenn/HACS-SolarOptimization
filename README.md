# Solar Optimizer

A Home Assistant custom integration that maximises self-consumption of solar energy by intelligently controlling hot water heating, car charging, and battery storage (Huawei LUNA).

## Features

- **Priority-based dispatch**: hot water → car charging → battery → grid export
- **8 kWh/day hot water target** — tracked from the smart plug's live power reading
- **forecast.solar integration** — pre-heats from grid/battery on low-sun days
- **Manual overrides** — force hot water or car charging from the dashboard
- **Dry-run mode** — logs decisions without toggling any physical switches
- **Custom Lovelace card** — auto-registered, zero manual resource setup

## Installation via HACS

1. In HACS → Integrations → ⋮ → Custom repositories  
   Add: `https://github.com/<your-username>/solar_optimizer` — Category: **Integration**
2. Install **Solar Optimizer** from HACS
3. Restart Home Assistant
4. Go to **Settings → Integrations → Add → Solar Optimizer** and follow the 4-step wizard
5. Reload your browser — the card is auto-registered

## Manual Installation

1. Copy `custom_components/solar_optimizer/` to your HA `config/custom_components/`
2. Restart Home Assistant
3. Add the integration via Settings → Integrations → Add → Solar Optimizer
4. If the card resource wasn't auto-registered, add it manually:  
   Settings → Dashboards → Resources → `/solar_optimizer/solar-optimizer-card.js` (Module)

## Lovelace Card

```yaml
type: custom:solar-optimizer-card
# prefix: solar_optimizer   # only needed if you renamed the integration domain
```

## Configuration

The 4-step wizard collects:

| Step | What you configure |
|------|--------------------|
| 1 — Forecast | Lat/lon, panel tilt, azimuth, kWp, optional API key |
| 2 — Sensors | Solar production, home consumption, battery SOC, hot water temp & power, car plugged-in |
| 3 — Switches | Hot water switch, car charger switch |
| 4 — Thresholds | Daily kWh target, surplus thresholds, battery SOC limits, pre-heat settings |

Thresholds can be updated any time via the **Configure** button in the card or Settings → Integrations → Solar Optimizer → Configure.

## Entities

| Entity | Description |
|--------|-------------|
| `sensor.solar_optimizer_mode` | Current state: idle / heating / charging / storing / preheat / error |
| `sensor.solar_optimizer_surplus_power` | Available surplus in W |
| `sensor.solar_optimizer_hot_water_kwh_today` | Energy delivered to hot water today |
| `sensor.solar_optimizer_forecast_today` | Predicted solar production for today (kWh) |
| `switch.solar_optimizer_force_hot_water` | Override: run hot water regardless of surplus |
| `switch.solar_optimizer_force_car_charge` | Override: run car charger regardless of surplus |
| `switch.solar_optimizer_dry_run` | Log decisions without toggling physical switches |

## Requirements

- Home Assistant 2023.1+
- [`huawei_solar`](https://github.com/wlcrs/huawei_solar) custom integration (for battery SOC entity)
- forecast.solar free account (optional API key for higher rate limits)
# HACS-SolarOptimization
