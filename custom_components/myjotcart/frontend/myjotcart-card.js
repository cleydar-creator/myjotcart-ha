// «MyJotCart» dashboard card: the whole MyJotCart app inside a dashboard.
// With the add-on it goes through ingress (same https address as Home Assistant), so it also works from outside home.
// Ingress needs a session cookie, which normally only the add-on's sidebar panel creates: this card creates it
// the same way (supervisor/api /ingress/session) and keeps it alive every minute, like the panel does.
// Without the add-on (MyJotCart on another machine) it shows the direct address instead.

const TEXT = {
  en: { loading: "Opening MyJotCart…", error: "Can't open MyJotCart", setup: "Set up the MyJotCart integration first." },
  es: { loading: "Abriendo MyJotCart…", error: "No se puede abrir MyJotCart", setup: "Configura primero la integración MyJotCart." },
  de: { loading: "MyJotCart wird geöffnet…", error: "MyJotCart kann nicht geöffnet werden", setup: "Richte zuerst die MyJotCart-Integration ein." },
  fr: { loading: "Ouverture de MyJotCart…", error: "Impossible d'ouvrir MyJotCart", setup: "Configurez d'abord l'intégration MyJotCart." },
  pt: { loading: "Abrindo o MyJotCart…", error: "Não foi possível abrir o MyJotCart", setup: "Configure primeiro a integração MyJotCart." },
};

class MyJotCartCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._started) {
      this._started = true;
      this._render();
      this._open();
    }
  }

  _t(key) {
    const lang = ((this._hass && this._hass.language) || "en").slice(0, 2);
    return (TEXT[lang] || TEXT.en)[key];
  }

  _render() {
    const height = this._config.height || "75vh";
    this.innerHTML = `
      <ha-card style="overflow:hidden;height:100%">
        <div class="mjc-msg" style="padding:24px;color:var(--secondary-text-color)">${this._t("loading")}</div>
        <iframe title="MyJotCart" allow="camera; clipboard-write; fullscreen"
          style="display:none;border:0;width:100%;height:${this._inPanel() ? "calc(100vh - var(--header-height, 56px))" : height}"></iframe>
      </ha-card>`;
  }

  _inPanel() {
    return !!this.closest && !!this.closest("hui-panel-view");
  }

  _ws(endpoint, method = "get", data) {
    const msg = { type: "supervisor/api", endpoint, method };
    if (data) msg.data = data;
    return this._hass.callWS(msg);
  }

  _setCookie(session) {
    document.cookie = `ingress_session=${session};path=/api/hassio_ingress/;SameSite=Strict${location.protocol === "https:" ? ";Secure" : ""}`;
  }

  async _session() {
    const res = await this._ws("/ingress/session", "post");
    this._sessionId = res.session;
    this._setCookie(res.session);
  }

  async _keepAlive() {
    try {
      await this._ws("/ingress/validate_session", "post", { session: this._sessionId });
      this._setCookie(this._sessionId);
    } catch (e) {
      await this._session().catch(() => {});
    }
  }

  async _open() {
    const msg = this.querySelector(".mjc-msg");
    const frame = this.querySelector("iframe");
    try {
      let src = this._config.url;
      if (!src) {
        let app;
        try {
          app = await this._hass.callWS({ type: "myjotcart/app" });
        } catch (e) {
          throw new Error(this._t("setup"));
        }
        const slug = this._config.addon || app.slug;
        if (slug) {
          const info = await this._ws(`/addons/${slug}/info`);
          await this._session();
          this._startTimer();
          src = info.ingress_url;
        } else {
          src = app.url;
        }
      }
      frame.src = src;
      frame.style.display = "block";
      msg.style.display = "none";
    } catch (e) {
      msg.innerHTML = `<b>${this._t("error")}</b><br>${(e && e.message) || e}`;
    }
  }

  _startTimer() {
    clearInterval(this._timer);
    this._timer = setInterval(() => this._keepAlive(), 60000);
  }

  connectedCallback() {
    if (this._sessionId) {
      this._keepAlive();
      this._startTimer();
    }
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    return 10;
  }

  getGridOptions() {
    return { columns: "full", rows: 10, min_rows: 4 };
  }

  static getStubConfig() {
    return {};
  }
}

if (!customElements.get("myjotcart-card")) {
  customElements.define("myjotcart-card", MyJotCartCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "myjotcart-card",
    name: "MyJotCart",
    description: "The whole MyJotCart app (lists, home pantry, scanner) in your dashboard — also from outside home.",
    preview: false,
    documentationURL: "https://github.com/cleydar-creator/myjotcart-ha",
  });
}
