const $ = (id) => document.getElementById(id);

function showErr(el, msg) {
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.hidden = false;
    el.classList.remove("feedback-ok");
    el.classList.add("feedback-err");
  } else {
    el.textContent = "";
    el.hidden = true;
    el.classList.remove("feedback-err", "feedback-ok");
  }
}

function showOk(el, msg) {
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.hidden = false;
    el.classList.remove("feedback-err");
    el.classList.add("feedback-ok");
  } else {
    el.textContent = "";
    el.hidden = true;
    el.classList.remove("feedback-err", "feedback-ok");
  }
}

let toastTimer = null;
function showToast(message, variant = "info") {
  const region = $("toastRegion");
  if (!region) return;
  const t = document.createElement("div");
  t.className = `toast toast-${variant}`;
  t.setAttribute("role", "status");
  t.textContent = message;
  region.appendChild(t);
  requestAnimationFrame(() => t.classList.add("toast-visible"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("toast-visible");
    setTimeout(() => t.remove(), 300);
  }, 4200);
}

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...opts,
  });
  const text = await r.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!r.ok) {
    const detail = data?.detail ?? text ?? r.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function navInit() {
  document.querySelectorAll(".app-nav button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-panel");
      document.querySelectorAll(".app-nav button").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`panel-${id}`).classList.add("active");
      if (id === "local") {
        loadLocalReactors().catch(() => {});
      }
    });
  });
}

let lastSettings = {};
let allSitesCache = [];
let sensorsCache = [];

function sensorLabel(s) {
  const name = s?.name || s?.code || "Sensor";
  const code = s?.code ? ` (${s.code})` : "";
  return name + code;
}

async function loadLocalSensors() {
  try {
    const data = await api("/api/sensors");
    sensorsCache = data.sensors || [];
  } catch {
    sensorsCache = [];
  }
}

async function syncSensors() {
  await api("/api/remote/sensors/sync", { method: "POST", body: "{}" });
  await loadLocalSensors();
}

async function loadSettings() {
  const s = await api("/api/settings");
  lastSettings = s;
  $("api_base_url").value = s.api_base_url || "";
  $("api_key").value = s.api_key || "";
  $("baud_rate").value = s.baud_rate || 9600;
  $("poll_interval_minutes").value = String(msToPollMinutes(s.poll_interval_ms ?? 1000));
  $("sync_interval_minutes").value = String(secToUploadMinutes(s.sync_interval_sec ?? 60));
  await refreshPorts(s.serial_port);
}

async function refreshPorts(selected) {
  const data = await api("/api/serial-ports");
  const sel = $("serial_port");
  sel.innerHTML = "";
  const ports = data.ports || [];
  if (!ports.length) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = "(no ports found)";
    sel.appendChild(o);
  } else {
    for (const p of ports) {
      const o = document.createElement("option");
      o.value = p;
      o.textContent = p;
      if (selected && p === selected) o.selected = true;
      sel.appendChild(o);
    }
  }
  if (selected && !ports.includes(selected)) {
    const o = document.createElement("option");
    o.value = selected;
    o.textContent = selected + " (saved)";
    o.selected = true;
    sel.appendChild(o);
  }
}

function numOrNull(v) {
  const n = Number(v);
  return Number.isFinite(n) && v !== "" ? n : null;
}

function msToPollMinutes(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return 1 / 60;
  return n / 60000;
}

function pollMinutesToMs(min) {
  const n = Number(min);
  if (!Number.isFinite(n)) return 1000;
  return Math.max(200, Math.round(n * 60000));
}

function secToUploadMinutes(sec) {
  const n = Number(sec);
  if (!Number.isFinite(n) || n <= 0) return 1;
  return n / 60;
}

function uploadMinutesToSec(min) {
  const n = Number(min);
  if (!Number.isFinite(n)) return 60;
  return Math.max(5, Math.round(n * 60));
}

function formatUploadTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
  } catch {
    return String(iso);
  }
}

function formatRuntimeStatus(st) {
  if (!st || typeof st !== "object") return "";
  const lines = [];
  lines.push(`<div class="runtime-line"><span class="rt-k">Service</span> <span class="rt-v">${st.running ? "Running" : "Stopped"}</span></div>`);
  lines.push(
    `<div class="runtime-line"><span class="rt-k">Serial</span> <span class="rt-v">${st.serial_open ? "Open" : "Closed / not connected"}</span></div>`,
  );
  if (st.last_poll_utc) {
    lines.push(
      `<div class="runtime-line"><span class="rt-k">Last poll</span> <span class="rt-v mono">${escapeHtml(String(st.last_poll_utc))}</span></div>`,
    );
  }
  lines.push(
    `<div class="runtime-line"><span class="rt-k">Queued uploads</span> <span class="rt-v">${st.pending_uploads ?? 0} packet(s)</span></div>`,
  );
  if (st.last_upload_success_utc) {
    lines.push(
      `<div class="runtime-line"><span class="rt-k">Last upload</span> <span class="rt-v">${escapeHtml(formatUploadTime(st.last_upload_success_utc))}${st.last_upload_detail ? ` — ${escapeHtml(String(st.last_upload_detail))}` : ""}</span></div>`,
    );
  }
  if (st.last_error) {
    lines.push(
      `<div class="runtime-line runtime-line-warn"><span class="rt-k">Notice</span> <span class="rt-v">${escapeHtml(String(st.last_error))}</span></div>`,
    );
  }
  return lines.join("");
}

async function saveSettings() {
  showErr($("settingsMsg"), "");
  const siteVal = $("site_select").value;
  const body = {
    api_base_url: $("api_base_url").value.trim(),
    api_key: $("api_key").value.trim(),
    serial_port: $("serial_port").value,
    baud_rate: Number($("baud_rate").value) || 9600,
    poll_interval_ms: pollMinutesToMs($("poll_interval_minutes").value),
    sync_interval_sec: uploadMinutesToSec($("sync_interval_minutes").value),
    selected_site_id: siteVal ? numOrNull(siteVal) : lastSettings.selected_site_id ?? null,
  };
  lastSettings = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
  showToast("Settings saved.", "success");
}

function populateSiteSelect() {
  const sel = $("site_select");
  const prev = sel.value;
  sel.innerHTML = "";

  if (!allSitesCache.length) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = "(load sites first)";
    sel.appendChild(o);
    return;
  }

  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "— Select site —";
  sel.appendChild(blank);

  for (const st of allSitesCache) {
    const o = document.createElement("option");
    o.value = String(st.id);
    const tz = st.timezone ? ` · ${st.timezone}` : "";
    o.textContent = `${st.name || st.slug || st.id} (#${st.id})${tz}`;
    sel.appendChild(o);
  }
  if (prev && allSitesCache.some((s) => String(s.id) === prev)) {
    sel.value = prev;
  } else if (lastSettings.selected_site_id != null) {
    const want = String(lastSettings.selected_site_id);
    if (allSitesCache.some((s) => String(s.id) === want)) sel.value = want;
  }
}

async function loadSites(options = {}) {
  showErr($("sitesMsg"), "");
  const data = await api("/api/remote/sites");
  allSitesCache = data.sites || [];
  populateSiteSelect();
  if (!options.silent) {
    showToast("Sites loaded from console.", "success");
  }
}

function renderRemoteReactorsSummary(reactors) {
  const box = $("remoteReactors");
  const wrap = $("remoteReactorsWrap");
  if (!reactors || !reactors.length) {
    box.innerHTML = "<div class=\"muted\">No reactors returned for this site.</div>";
    if (wrap) wrap.hidden = false;
    return;
  }
  if (wrap) wrap.hidden = false;
  box.innerHTML = reactors
    .map(
      (r) =>
        `<div class="sites-reactor-row"><strong>${escapeHtml(r.name)}</strong> <span class="muted">console id</span> <code>${r.id}</code></div>`,
    )
    .join("");
}

async function syncReactorsForSite(siteId) {
  const data = await api("/api/local-reactors/sync", {
    method: "POST",
    body: JSON.stringify({ site_id: siteId }),
  });
  lastSettings = { ...lastSettings, selected_site_id: siteId };
  renderRemoteReactorsSummary(data.reactors || []);
  await loadLocalReactors();
  showToast("Reactors synced for this site.", "success");
}

async function onSiteSelectionChanged() {
  const siteId = numOrNull($("site_select").value);
  showErr($("sitesMsg"), "");
  if (!siteId) {
    $("remoteReactors").innerHTML = "";
    const wrap = $("remoteReactorsWrap");
    if (wrap) wrap.hidden = true;
    try {
      lastSettings = await api("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({ selected_site_id: null }),
      });
    } catch {
      lastSettings = { ...lastSettings, selected_site_id: null };
    }
    await loadLocalReactors();
    return;
  }
  try {
    await syncReactorsForSite(siteId);
  } catch (e) {
    showErr($("sitesMsg"), String(e.message || e));
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** At-a-glance table of provisioned Modbus devices (uses sensorsCache for friendly type names when available). */
function renderDeviceSummaryHtml(devs) {
  if (!devs || !devs.length) {
    return `<div class="reactor-device-summary-inner"><p class="reactor-summary-empty muted">No sensors provisioned yet. Use <strong>Configure sensors &amp; Modbus</strong> below to add devices.</p></div>`;
  }
  const sorted = [...devs].sort((a, b) => a.id - b.id);
  const rows = sorted
    .map((d) => {
      const sensor = sensorsCache.find((s) => s.code === d.kind);
      const typeLabel = sensor ? sensorLabel(sensor) : d.kind;
      const nameCell = escapeHtml(d.name || typeLabel);
      return `<tr>
      <td>${nameCell}</td>
      <td class="mono muted">${escapeHtml(typeLabel)}</td>
      <td class="mono reactor-slave-cell"><strong>${d.slave_id}</strong></td>
    </tr>`;
    })
    .join("");
  return `<div class="reactor-device-summary-inner reactor-summary-wrap">
      <p class="reactor-summary-title">Provisioned sensors</p>
      <div class="table-scroll">
        <table class="reactor-summary-table">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Sensor type</th>
              <th scope="col">Modbus address <span class="th-sub">(slave ID)</span></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

async function refreshReactorDeviceSummary(wrap, reactorId) {
  const box = wrap.querySelector(".reactor-device-summary");
  if (!box) return;
  try {
    await loadLocalSensors();
    const devs = await api(`/api/local-reactors/${reactorId}/devices`);
    box.innerHTML = renderDeviceSummaryHtml(devs);
  } catch {
    box.innerHTML =
      '<div class="reactor-device-summary-inner"><p class="muted">Could not load device list.</p></div>';
  }
}

async function loadLocalReactors() {
  const rows = await api("/api/local-reactors");
  const host = $("reactorList");
  const empty = $("reactorListEmpty");
  host.innerHTML = "";
  if (!rows.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  for (const r of rows) {
    host.appendChild(renderReactorCard(r));
  }
}

function renderReactorCard(r) {
  const wrap = document.createElement("article");
  wrap.className = "card card-nested reactor-card";
  wrap.dataset.reactorId = String(r.id);
  const devices = r.devices || [];
  wrap.innerHTML = `
    <div class="reactor-card-head">
      <h3>${escapeHtml(r.label)}</h3>
      <p class="reactor-meta mono muted">
        Console reactor id <strong>${r.server_reactor_id ?? "—"}</strong>
        · Site id <strong>${r.site_id ?? "—"}</strong>
      </p>
    </div>
    <div class="reactor-device-summary" aria-label="Provisioned sensors for this reactor">
      ${renderDeviceSummaryHtml(devices)}
    </div>
    <div class="reactor-card-actions">
      <div class="field field-inline">
        <label for="lr-en-${r.id}">Include in monitoring</label>
        <select id="lr-en-${r.id}" class="lr-en" aria-describedby="lr-help-${r.id}">
          <option value="true" ${r.enabled ? "selected" : ""}>Yes</option>
          <option value="false" ${!r.enabled ? "selected" : ""}>No</option>
        </select>
      </div>
      <p id="lr-help-${r.id}" class="field-hint">Turn off to skip this reactor while polling.</p>
      <div class="toolbar reactor-toolbar">
        <button type="button" class="btn secondary lr-save">Apply polling</button>
        <button type="button" class="btn primary lr-devices">Configure sensors &amp; Modbus</button>
      </div>
    </div>
    <div class="lr-dev-panel" hidden></div>
  `;
  wrap.querySelector(".lr-save").addEventListener("click", () => saveReactorEnabled(wrap, r.id));
  wrap.querySelector(".lr-devices").addEventListener("click", () => toggleDevices(wrap, r.id));
  return wrap;
}

async function saveReactorEnabled(wrap, id) {
  await api(`/api/local-reactors/${id}`, {
    method: "PATCH",
    body: JSON.stringify({
      enabled: wrap.querySelector(".lr-en").value === "true",
    }),
  });
  await loadLocalReactors();
  showToast("Polling preference saved for this reactor.", "success");
}

async function toggleDevices(wrap, reactorId) {
  const panel = wrap.querySelector(".lr-dev-panel");
  const btn = wrap.querySelector(".lr-devices");
  if (!panel.hidden) {
    panel.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    return;
  }
  panel.hidden = false;
  btn.setAttribute("aria-expanded", "true");
  await loadLocalSensors();
  await refreshReactorDeviceSummary(wrap, reactorId);
  await refreshDevicePanel(wrap, reactorId);
  const first = panel.querySelector("select, input, button");
  if (first) first.focus();
}

async function refreshDevicePanel(wrap, reactorId) {
  const panel = wrap.querySelector(".lr-dev-panel");
  const devs = await api(`/api/local-reactors/${reactorId}/devices`);
  await loadLocalSensors();
  const uid = `lr-${reactorId}`;
  panel.innerHTML = `
    <div class="device-panel-header">
      <h4 class="subheading">Sensors on this reactor</h4>
      <p class="field-hint">
        Adding or removing a device saves <strong>immediately</strong> to this hub. You do not need to use
        <strong>Save settings</strong> on the Settings tab.
      </p>
    </div>
    <div class="table-scroll device-table-wrap">
      <table>
        <thead><tr><th>Sensor</th><th>Name</th><th>Slave ID</th><th></th></tr></thead>
        <tbody class="dev-rows"></tbody>
      </table>
    </div>
    <div class="device-add-form">
      <p class="device-add-title">Add Modbus device</p>
      <div class="device-add-grid">
        <div class="field">
          <label for="${uid}-kind">Sensor type</label>
          <select id="${uid}-kind" class="nd-kind"></select>
        </div>
        <div class="field">
          <label for="${uid}-slave">Slave ID (1–247)</label>
          <input id="${uid}-slave" class="nd-slave" type="number" min="1" max="247" value="1" />
        </div>
        <div class="field device-add-actions">
          <button type="button" class="btn secondary nd-sync">Sync sensor list from console</button>
          <button type="button" class="btn primary nd-add">Add device</button>
        </div>
      </div>
    </div>
    <p class="lr-sensor-msg feedback-msg" hidden></p>
  `;

  const tbody = panel.querySelector(".dev-rows");
  const kindSel = panel.querySelector(".nd-kind");
  const msg = panel.querySelector(".lr-sensor-msg");

  kindSel.innerHTML = "";
  if (!sensorsCache.length) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = "(sync sensors first)";
    kindSel.appendChild(o);
  } else {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "— Choose sensor —";
    kindSel.appendChild(blank);
    for (const s of sensorsCache) {
      const o = document.createElement("option");
      o.value = s.code;
      o.textContent = sensorLabel(s);
      kindSel.appendChild(o);
    }
  }

  panel.querySelector(".nd-sync").addEventListener("click", async () => {
    showErr(msg, "");
    try {
      await syncSensors();
      await refreshReactorDeviceSummary(wrap, reactorId);
      await refreshDevicePanel(wrap, reactorId);
      showToast("Sensor definitions updated.", "success");
    } catch (e) {
      showErr(msg, String(e.message || e));
    }
  });

  for (const d of devs) {
    const sensor = sensorsCache.find((s) => s.code === d.kind);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(sensor ? sensorLabel(sensor) : d.kind)}</td>
      <td>${escapeHtml(d.name)}</td>
      <td class="mono">${d.slave_id}</td>
      <td><button type="button" class="btn danger btn-sm rm">Remove</button></td>
    `;
    tr.querySelector(".rm").addEventListener("click", async () => {
      await api(`/api/devices/${d.id}`, { method: "DELETE" });
      await refreshReactorDeviceSummary(wrap, reactorId);
      await refreshDevicePanel(wrap, reactorId);
      showToast("Device removed.", "success");
    });
    tbody.appendChild(tr);
  }

  panel.querySelector(".nd-add").addEventListener("click", async () => {
    const kind = panel.querySelector(".nd-kind").value;
    showErr(msg, "");
    if (!kind) {
      showErr(msg, "Choose a sensor type, or sync sensors from the console first.");
      return;
    }
    const sensor = sensorsCache.find((s) => s.code === kind);
    const name = sensor?.name || sensor?.code || kind;
    const slave_id = Number(panel.querySelector(".nd-slave").value) || 1;
    await api(`/api/local-reactors/${reactorId}/devices`, {
      method: "POST",
      body: JSON.stringify({ kind, name, slave_id, custom_config_json: null }),
    });
    await refreshReactorDeviceSummary(wrap, reactorId);
    await refreshDevicePanel(wrap, reactorId);
    showToast("Device added and saved.", "success");
  });
}

async function pollLive() {
  try {
    const data = await api("/api/live");
    const st = data.status || {};
    const pill = $("headerStatus");
    pill.textContent = st.running ? "Running" : "Stopped";
    pill.className = "pill " + (st.running ? "ok" : "pill-idle");
    const rs = $("runtimeStatus");
    if (rs) rs.innerHTML = formatRuntimeStatus(st);

    const pending = st.pending_uploads ?? 0;
    const pendingEl = $("syncPendingCount");
    if (pendingEl) {
      pendingEl.textContent =
        pending === 0
          ? "0 readings waiting (queue empty)"
          : `${pending} reading packet(s) waiting to upload`;
    }
    const queueLine = $("syncQueueLine");
    if (queueLine) {
      queueLine.classList.toggle("sync-queue-backlog", pending > 0);
    }
    const lastEl = $("syncLastUpload");
    if (lastEl) {
      const detail = st.last_upload_detail ? ` — ${st.last_upload_detail}` : "";
      lastEl.textContent = st.last_upload_success_utc
        ? `${formatUploadTime(st.last_upload_success_utc)}${detail}`
        : st.pending_uploads > 0
          ? "None yet (offline or still syncing)"
          : "None yet";
    }

    const body = $("liveBody");
    const snaps = data.snapshots || [];
    const liveEmpty = $("liveEmpty");
    body.innerHTML = "";
    if (liveEmpty) liveEmpty.hidden = snaps.length > 0;
    for (const s of snaps) {
      const tr = document.createElement("tr");
      const spec = s.spectral ? s.spectral.join(", ") : "—";
      const custom = s.custom ? JSON.stringify(s.custom) : "—";
      tr.innerHTML = `
        <td>${escapeHtml(s.label)}</td>
        <td>${s.server_reactor_id ?? "—"}</td>
        <td>${s.ph != null ? s.ph.toFixed(2) : "—"}</td>
        <td>${s.temperature_c != null ? s.temperature_c.toFixed(1) : "—"}</td>
        <td class="mono">${escapeHtml(spec)}</td>
        <td class="mono">${escapeHtml(custom)}</td>
        <td>${s.error ? escapeHtml(s.error) : "ok"}</td>
      `;
      body.appendChild(tr);
    }
    showErr($("liveError"), "");
  } catch (e) {
    showErr($("liveError"), String(e.message || e));
  }
}

async function refreshOutbox() {
  showErr($("outboxError"), "");
  try {
    const data = await api("/api/outbox?limit=100");
    const total = data.total_pending ?? 0;
    const shown = data.rows?.length ?? 0;
    $("outboxCount").textContent =
      total === 0
        ? "Queue empty"
        : `${total} pending` + (shown < total ? ` (showing first ${shown})` : "");
    const body = $("outboxBody");
    body.innerHTML = "";
    for (const r of data.rows || []) {
      const tr = document.createElement("tr");
      const err = r.last_error ? String(r.last_error) : "";
      const at = r.reading_at ? String(r.reading_at) : "—";
      const preview = r.payload_preview ? String(r.payload_preview) : "";
      tr.innerHTML = `
        <td class="mono">${r.id}</td>
        <td class="mono">${r.reactor_id}</td>
        <td class="mono">${escapeHtml(at)}</td>
        <td class="mono">${r.attempts ?? 0}</td>
        <td>${escapeHtml(err)}</td>
        <td class="mono">${escapeHtml(preview)}</td>
      `;
      body.appendChild(tr);
    }
  } catch (e) {
    showErr($("outboxError"), String(e.message || e));
  }
}

async function init() {
  navInit();
  try {
    await api("/api/health");
    $("headerStatus").textContent = "Idle";
    $("headerStatus").className = "pill pill-idle";
  } catch {
    $("headerStatus").textContent = "API down";
    $("headerStatus").className = "pill pill-bad";
  }

  await loadSettings();
  await loadLocalSensors();

  $("btnRefreshPorts").addEventListener("click", () => refreshPorts($("serial_port").value));
  $("btnSaveSettings").addEventListener("click", async () => {
    try {
      await saveSettings();
      showErr($("settingsMsg"), "");
    } catch (e) {
      showErr($("settingsMsg"), String(e.message || e));
    }
  });

  $("btnStart").addEventListener("click", async () => {
    await api("/api/control/start", { method: "POST", body: "{}" });
    showToast("Monitoring started.", "success");
  });
  $("btnStop").addEventListener("click", async () => {
    await api("/api/control/stop", { method: "POST", body: "{}" });
    showToast("Monitoring stopped.", "info");
  });

  $("btnRefreshOutbox").addEventListener("click", () => refreshOutbox());

  $("btnLoadSites").addEventListener("click", async () => {
    try {
      await loadSites();
      if (lastSettings.selected_site_id != null) {
        const want = String(lastSettings.selected_site_id);
        if ($("site_select").querySelector(`option[value="${want}"]`)) {
          $("site_select").value = want;
          await onSiteSelectionChanged();
        }
      }
    } catch (e) {
      showErr($("sitesMsg"), String(e.message || e));
    }
  });

  $("site_select").addEventListener("change", () => onSiteSelectionChanged());

  const hasCreds = () => $("api_base_url").value.trim() && $("api_key").value.trim();

  if (hasCreds()) {
    try {
      await loadSites({ silent: true });
      try {
        await syncSensors();
      } catch {
        // sync later from reactor panels
      }
      if (lastSettings.selected_site_id != null) {
        const want = String(lastSettings.selected_site_id);
        if ($("site_select").querySelector(`option[value="${want}"]`)) {
          $("site_select").value = want;
          await syncReactorsForSite(lastSettings.selected_site_id, { silent: true });
        }
      } else {
        await loadLocalReactors();
      }
    } catch {
      await loadLocalReactors();
    }
  } else {
    await loadLocalReactors();
  }

  setInterval(pollLive, 1500);
  setInterval(refreshOutbox, 3000);
  pollLive();
  refreshOutbox();
}

init();
