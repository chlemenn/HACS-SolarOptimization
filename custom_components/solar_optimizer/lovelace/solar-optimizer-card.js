/**
 * Solar Optimizer Card — custom Lovelace element
 *
 * Config (lovelace YAML):
 *   type: custom:solar-optimizer-card
 *   prefix: solar_optimizer   # optional, default: "solar_optimizer"
 */

const DEFAULT_PREFIX = "solar_optimizer";

const MODE_LABELS = {
  idle:     { text: "IDLE",     color: "#888888" },
  heating:  { text: "HEATING",  color: "#52b788" },
  charging: { text: "CHARGING", color: "#90e0ef" },
  storing:  { text: "STORING",  color: "#f0a500" },
  preheat:  { text: "PRE-HEAT", color: "#f77f00" },
  error:    { text: "ERROR",    color: "#e63946" },
};

class SolarOptimizerCard extends HTMLElement {
  // ── Lovelace lifecycle ──────────────────────────────────────────────────────

  setConfig(config) {
    this._prefix = config.prefix || DEFAULT_PREFIX;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  // ── Entity ID helpers ───────────────────────────────────────────────────────

  _sensor(suffix) {
    return `sensor.${this._prefix}_${suffix}`;
  }

  _switch(suffix) {
    return `switch.${this._prefix}_${suffix}`;
  }

  // ── State helpers ───────────────────────────────────────────────────────────

  _state(entityId, fallback = null) {
    const s = this._hass && this._hass.states[entityId];
    if (!s || ["unavailable", "unknown", ""].includes(s.state)) return fallback;
    return s.state;
  }

  _floatState(entityId, fallback = 0) {
    const v = parseFloat(this._state(entityId, fallback));
    return isNaN(v) ? fallback : v;
  }

  _isOn(entityId) {
    return this._state(entityId) === "on";
  }

  _attrs(entityId) {
    const s = this._hass && this._hass.states[entityId];
    return s ? s.attributes : {};
  }

  // ── Service calls ───────────────────────────────────────────────────────────

  _toggle(entityId) {
    if (!this._hass) return;
    this._hass.callService("switch", "toggle", { entity_id: entityId });
  }

  _openConfig() {
    const event = new CustomEvent("hass-navigate", {
      detail: { path: "/config/integrations" },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  // ── Rendering ───────────────────────────────────────────────────────────────

  _render() {
    if (!this.shadowRoot || !this._hass) return;

    const modeEntityId = this._sensor("mode");
    const attrs = this._attrs(modeEntityId);
    const modeState = this._state(modeEntityId, "idle");

    const solarW    = attrs.solar_production_w   ?? 0;
    const homeW     = attrs.home_consumption_w   ?? 0;
    const surplusW  = attrs.surplus_power_w      ?? (solarW - homeW);
    const battSoc   = attrs.battery_soc          ?? this._floatState(this._sensor("battery_soc"), 0);
    const carIn     = attrs.car_plugged_in       ?? false;
    const hwOn      = attrs.hot_water_on         ?? false;
    const carOn     = attrs.car_charger_on       ?? false;
    const hwKwh     = attrs.hot_water_kwh_today  ?? this._floatState(this._sensor("hot_water_kwh_today"), 0);
    const hwTarget  = attrs.hot_water_target_kwh ?? 8.0;
    const forecastKwh = attrs.forecast_today_kwh ?? this._floatState(this._sensor("forecast_today"), 0);

    const forceHwOn  = this._isOn(this._switch("force_hot_water"));
    const forceCarOn = this._isOn(this._switch("force_car_charge"));

    const hwProgress = Math.min((hwKwh / hwTarget) * 100, 100);
    const modeMeta = MODE_LABELS[modeState] || MODE_LABELS.idle;

    // ── Format helpers ──────────────────────────────────────────────────────
    const fmtW = (w) => {
      const abs = Math.abs(w);
      if (abs >= 1000) return `${(w / 1000).toFixed(1)} kW`;
      return `${Math.round(w)} W`;
    };
    const fmtKwh = (k) => `${parseFloat(k).toFixed(2)} kWh`;

    // ── Car/battery status display ──────────────────────────────────────────
    const carLabel = !carIn  ? "not plugged in"
                   : carOn   ? "charging ⚡"
                   : "standby";
    const carColor = carOn ? "#52b788" : carIn ? "#f0a500" : "#666";

    // ── Surplus colour ──────────────────────────────────────────────────────
    const surplusColor = surplusW > 0 ? "#52b788" : "#e63946";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--primary-font-family, sans-serif);
        }
        ha-card {
          padding: 0;
          overflow: hidden;
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px 8px;
          border-bottom: 1px solid rgba(255,255,255,0.07);
        }
        .card-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--primary-text-color);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .card-title ha-icon {
          --mdc-icon-size: 18px;
          color: #f0a500;
        }
        .mode-badge {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.5px;
          padding: 2px 8px;
          border-radius: 10px;
          background: rgba(255,255,255,0.08);
          color: ${modeMeta.color};
          border: 1px solid ${modeMeta.color}44;
        }
        .power-grid {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 1px;
          background: rgba(255,255,255,0.05);
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .power-tile {
          padding: 10px 12px;
          background: var(--card-background-color, #1c1c1c);
          text-align: center;
        }
        .power-value {
          font-size: 18px;
          font-weight: 700;
          line-height: 1.2;
        }
        .power-label {
          font-size: 9px;
          font-weight: 600;
          letter-spacing: 0.8px;
          color: var(--secondary-text-color, #888);
          margin-top: 2px;
        }
        .section {
          padding: 10px 16px;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .hw-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
        }
        .hw-label {
          font-size: 12px;
          color: var(--primary-text-color);
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .hw-status {
          width: 8px; height: 8px;
          border-radius: 50%;
          background: ${hwOn ? "#52b788" : "#444"};
          display: inline-block;
        }
        .hw-value {
          font-size: 12px;
          color: var(--secondary-text-color, #888);
        }
        .progress-track {
          width: 100%;
          height: 6px;
          background: rgba(255,255,255,0.08);
          border-radius: 4px;
          overflow: hidden;
        }
        .progress-fill {
          height: 100%;
          width: ${hwProgress}%;
          background: ${hwProgress >= 100 ? "#52b788" : "linear-gradient(90deg, #2d6a4f, #52b788)"};
          border-radius: 4px;
          transition: width 0.5s ease;
        }
        .forecast-note {
          font-size: 10px;
          color: var(--secondary-text-color, #888);
          margin-top: 4px;
          text-align: right;
        }
        .device-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1px;
          background: rgba(255,255,255,0.05);
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .device-tile {
          padding: 8px 12px;
          background: var(--card-background-color, #1c1c1c);
        }
        .device-name {
          font-size: 10px;
          letter-spacing: 0.5px;
          color: var(--secondary-text-color, #888);
          margin-bottom: 2px;
        }
        .device-value {
          font-size: 13px;
          font-weight: 600;
        }
        .override-row {
          display: flex;
          gap: 8px;
          padding: 10px 16px 8px;
          align-items: center;
        }
        .btn {
          flex: 1;
          padding: 6px 8px;
          border: none;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          transition: opacity 0.15s;
          letter-spacing: 0.3px;
        }
        .btn:active { opacity: 0.7; }
        .btn-hw {
          background: ${forceHwOn ? "#1b4332" : "rgba(255,255,255,0.06)"};
          color: ${forceHwOn ? "#52b788" : "var(--secondary-text-color, #888)"};
          border: 1px solid ${forceHwOn ? "#52b788" : "transparent"};
        }
        .btn-car {
          background: ${forceCarOn ? "#0a2a3a" : "rgba(255,255,255,0.06)"};
          color: ${forceCarOn ? "#90e0ef" : "var(--secondary-text-color, #888)"};
          border: 1px solid ${forceCarOn ? "#90e0ef" : "transparent"};
        }
        .btn-config {
          flex: 0 0 auto;
          background: rgba(255,255,255,0.04);
          color: var(--secondary-text-color, #888);
          border: 1px solid rgba(255,255,255,0.08);
          padding: 6px 10px;
        }
      </style>

      <ha-card>
        <div class="card-header">
          <div class="card-title">
            <ha-icon icon="mdi:solar-power"></ha-icon>
            Solar Optimizer
          </div>
          <span class="mode-badge">${modeMeta.text}</span>
        </div>

        <div class="power-grid">
          <div class="power-tile">
            <div class="power-value" style="color:#f0a500">${fmtW(solarW)}</div>
            <div class="power-label">SOLAR</div>
          </div>
          <div class="power-tile">
            <div class="power-value" style="color:var(--primary-text-color)">${fmtW(homeW)}</div>
            <div class="power-label">HOME</div>
          </div>
          <div class="power-tile">
            <div class="power-value" style="color:${surplusColor}">${fmtW(surplusW)}</div>
            <div class="power-label">SURPLUS</div>
          </div>
        </div>

        <div class="section">
          <div class="hw-row">
            <div class="hw-label">
              <span class="hw-status"></span>
              Hot Water
            </div>
            <div class="hw-value">${fmtKwh(hwKwh)} / ${fmtKwh(hwTarget)}</div>
          </div>
          <div class="progress-track">
            <div class="progress-fill"></div>
          </div>
          <div class="forecast-note">☀ Forecast today: ${fmtKwh(forecastKwh)}</div>
        </div>

        <div class="device-grid">
          <div class="device-tile">
            <div class="device-name">🚗 CAR</div>
            <div class="device-value" style="color:${carColor}">${carLabel}</div>
          </div>
          <div class="device-tile">
            <div class="device-name">🔋 BATTERY</div>
            <div class="device-value" style="color:${battSoc > 50 ? '#52b788' : battSoc > 20 ? '#f0a500' : '#e63946'}">${Math.round(battSoc)} %</div>
          </div>
        </div>

        <div class="override-row">
          <button class="btn btn-hw" id="btn-hw">
            ${forceHwOn ? "✓" : ""} Force Hot Water
          </button>
          <button class="btn btn-car" id="btn-car">
            ${forceCarOn ? "✓" : ""} Force Car
          </button>
          <button class="btn btn-config" id="btn-config" title="Configure">⚙</button>
        </div>
      </ha-card>
    `;

    // Attach button listeners after innerHTML is set
    this.shadowRoot.getElementById("btn-hw")
      ?.addEventListener("click", () => this._toggle(this._switch("force_hot_water")));
    this.shadowRoot.getElementById("btn-car")
      ?.addEventListener("click", () => this._toggle(this._switch("force_car_charge")));
    this.shadowRoot.getElementById("btn-config")
      ?.addEventListener("click", () => this._openConfig());
  }

  // ── Card editor metadata ────────────────────────────────────────────────────

  static getConfigElement() {
    return document.createElement("solar-optimizer-card-editor");
  }

  static getStubConfig() {
    return { prefix: DEFAULT_PREFIX };
  }

  getCardSize() {
    return 4;
  }
}

customElements.define("solar-optimizer-card", SolarOptimizerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "solar-optimizer-card",
  name: "Solar Optimizer",
  description: "Live dashboard for the Solar Optimizer integration",
  preview: false,
});
