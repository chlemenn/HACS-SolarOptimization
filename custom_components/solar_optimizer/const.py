"""Constants for Solar Optimizer."""

DOMAIN = "solar_optimizer"

# ── Configuration keys: Forecast ──────────────────────────────────────────────
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_DECLINATION = "declination"   # panel tilt in degrees
CONF_AZIMUTH = "azimuth"           # panel azimuth in degrees
CONF_KWP = "kwp"                   # installed peak power in kWp
CONF_API_KEY = "api_key"           # forecast.solar API key (optional)

# ── Configuration keys: Sensors ───────────────────────────────────────────────
CONF_SOLAR_PRODUCTION = "solar_production_entity"
CONF_HOME_CONSUMPTION = "home_consumption_entity"
CONF_BATTERY_SOC = "battery_soc_entity"
CONF_HOT_WATER_TEMP = "hot_water_temp_entity"
CONF_HOT_WATER_POWER = "hot_water_power_entity"
CONF_CAR_PLUGGED_IN = "car_plugged_in_entity"

# ── Configuration keys: Switches ──────────────────────────────────────────────
CONF_HOT_WATER_SWITCH = "hot_water_switch_entity"
CONF_CAR_CHARGER_SWITCH = "car_charger_switch_entity"

# ── Configuration keys: Thresholds ────────────────────────────────────────────
CONF_HOT_WATER_DAILY_TARGET = "hot_water_daily_target_kwh"
CONF_THERMAL_SAFETY_MAX = "thermal_safety_max_celsius"
CONF_HOT_WATER_MIN_SURPLUS = "hot_water_min_surplus_w"
CONF_CAR_MIN_SURPLUS = "car_min_surplus_w"
CONF_BATTERY_MIN_SOC = "battery_min_soc"
CONF_BATTERY_MAX_SOC = "battery_max_soc"
CONF_FORECAST_PREHEAT_THRESHOLD = "forecast_preheat_threshold_kwh"
CONF_PREHEAT_DEADLINE = "preheat_deadline"

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_HOT_WATER_DAILY_TARGET = 8.0        # kWh
DEFAULT_THERMAL_SAFETY_MAX = 65.0           # °C
DEFAULT_HOT_WATER_MIN_SURPLUS = 500         # W
DEFAULT_CAR_MIN_SURPLUS = 1400              # W
DEFAULT_BATTERY_MIN_SOC = 10                # %
DEFAULT_BATTERY_MAX_SOC = 95                # %
DEFAULT_FORECAST_PREHEAT_THRESHOLD = 4.0    # kWh
DEFAULT_PREHEAT_DEADLINE = "10:00:00"

# ── Optimizer modes ───────────────────────────────────────────────────────────
MODE_IDLE = "idle"
MODE_HEATING = "heating"
MODE_CHARGING = "charging"
MODE_STORING = "storing"
MODE_PREHEAT = "preheat"
MODE_ERROR = "error"

# ── Update intervals ──────────────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 60
FORECAST_UPDATE_INTERVAL_SECONDS = 1800    # 30 minutes

# ── forecast.solar ────────────────────────────────────────────────────────────
FORECAST_SOLAR_BASE_URL = "https://api.forecast.solar"
FORECAST_CACHE_MAX_AGE_SECONDS = 86400     # 24 hours fallback
