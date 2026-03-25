const $ = (id) => document.getElementById(id);

function showErr(el, msg) {
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.hidden = false;
  } else {
    el.textContent = "";
    el.hidden = true;
  }
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
  $("poll_interval_ms").value = s.poll_interval_ms || 1000;
  $("sync_interval_sec").value = s.sync_interval_sec || 60;
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

async function saveSettings() {
  showErr($("settingsMsg"), "");
  const siteVal = $("site_select").value;
  const body = {
    api_base_url: $("api_base_url").value.trim(),
    api_key: $("api_key").value.trim(),
    serial_port: $("serial_port").value,
    baud_rate: Number($("baud_rate").value) || 9600,
    poll_interval_ms: Number($("poll_interval_ms").value) || 1000,
    sync_interval_sec: Number($("sync_interval_sec").value) || 60,
    selected_site_id: siteVal ? numOrNull(siteVal) : lastSettings.selected_site_id ?? null,
  };
  lastSettings = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
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
    o.textContent = `${st.name || st.slug || st.id} (#${st.id})`;
    sel.appendChild(o);
  }
  if (prev && allSitesCache.some((s) => String(s.id) === prev)) {
    sel.value = prev;
  } else if (lastSettings.selected_site_id != null) {
    const want = String(lastSettings.selected_site_id);
    if (allSitesCache.some((s) => String(s.id) === want)) sel.value = want;
  }
}

async function loadSites() {
  showErr($("sitesMsg"), "");
  const data = await api("/api/remote/sites");
  allSitesCache = data.sites || [];
  populateSiteSelect();
}

function renderRemoteReactorsSummary(reactors) {
  const box = $("remoteReactors");
  if (!reactors || !reactors.length) {
    box.innerHTML = "<div>No reactors returned for this site.</div>";
    return;
  }
  box.innerHTML = reactors
    .map(
      (r) =>
        `<div><strong>${escapeHtml(r.name)}</strong> — console id <code>${r.id}</code></div>`,
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
}

async function onSiteSelectionChanged() {
  const siteId = numOrNull($("site_select").value);
  showErr($("sitesMsg"), "");
  if (!siteId) {
    $("remoteReactors").innerHTML = "";
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
  const wrap = document.createElement("div");
  wrap.className = "card card-nested";
  wrap.dataset.reactorId = String(r.id);
  wrap.innerHTML = `
    <h3>${escapeHtml(r.label)}</h3>
    <p class="mono muted" style="margin:0 0 0.75rem;font-size:0.875rem">
      Console reactor id <strong>${r.server_reactor_id ?? "—"}</strong>
      · Site id <strong>${r.site_id ?? "—"}</strong>
    </p>
    <div class="field">
      <label>Polling enabled</label>
      <select class="lr-en">
        <option value="true" ${r.enabled ? "selected" : ""}>yes</option>
        <option value="false" ${!r.enabled ? "selected" : ""}>no</option>
      </select>
    </div>
    <div class="toolbar">
      <button type="button" class="btn primary lr-save">Save</button>
      <button type="button" class="btn lr-devices">Devices…</button>
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
}

async function toggleDevices(wrap, reactorId) {
  const panel = wrap.querySelector(".lr-dev-panel");
  if (!panel.hidden) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  await loadLocalSensors();
  await refreshDevicePanel(wrap, reactorId);
}

async function refreshDevicePanel(wrap, reactorId) {
  const panel = wrap.querySelector(".lr-dev-panel");
  const devs = await api(`/api/local-reactors/${reactorId}/devices`);
  await loadLocalSensors();
  panel.innerHTML = `
    <h4 class="subheading" style="margin:0.5rem 0">Devices</h4>
    <p class="lead muted" style="margin:0 0 0.75rem">Add configured device</p>
    <table>
      <thead><tr><th>Kind</th><th>Name</th><th>Slave</th><th></th></tr></thead>
      <tbody class="dev-rows"></tbody>
    </table>
    <div class="toolbar" style="margin-top:0.75rem">
      <button type="button" class="btn nd-sync">Sync sensors</button>
      <select class="nd-kind"></select>
      <input class="nd-slave" type="number" min="1" max="247" value="1" style="max-width:100px" />
      <button type="button" class="btn primary nd-add">Add device</button>
    </div>
    <div class="err" id="sensorMsg" hidden></div>
  `;

  const tbody = panel.querySelector(".dev-rows");
  const kindSel = panel.querySelector(".nd-kind");
  const msg = panel.querySelector("#sensorMsg");

  kindSel.innerHTML = "";
  if (!sensorsCache.length) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = "(sync sensors first)";
    kindSel.appendChild(o);
  } else {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "— Select sensor —";
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
      await refreshDevicePanel(wrap, reactorId);
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
      <td>${d.slave_id}</td>
      <td><button type="button" class="btn danger rm">Remove</button></td>
    `;
    tr.querySelector(".rm").addEventListener("click", async () => {
      await api(`/api/devices/${d.id}`, { method: "DELETE" });
      await refreshDevicePanel(wrap, reactorId);
    });
    tbody.appendChild(tr);
  }

  panel.querySelector(".nd-add").addEventListener("click", async () => {
    const kind = panel.querySelector(".nd-kind").value;
    showErr(msg, "");
    if (!kind) {
      showErr(msg, "Select a sensor first (or sync sensors).");
      return;
    }
    const sensor = sensorsCache.find((s) => s.code === kind);
    const name = sensor?.name || sensor?.code || kind;
    const slave_id = Number(panel.querySelector(".nd-slave").value) || 1;
    await api(`/api/local-reactors/${reactorId}/devices`, {
      method: "POST",
      body: JSON.stringify({ kind, name, slave_id, custom_config_json: null }),
    });
    await refreshDevicePanel(wrap, reactorId);
  });
}

async function pollLive() {
  try {
    const data = await api("/api/live");
    const st = data.status || {};
    const pill = $("headerStatus");
    pill.textContent = st.running ? "Running" : "Stopped";
    pill.className = "pill " + (st.running ? "ok" : "pill-idle");
    $("runtimeStatus").textContent = JSON.stringify(st, null, 2);

    const body = $("liveBody");
    body.innerHTML = "";
    for (const s of data.snapshots || []) {
      const tr = document.createElement("tr");
      const spec = s.spectral ? s.spectral.join(", ") : "—";
      tr.innerHTML = `
        <td>${escapeHtml(s.label)}</td>
        <td>${s.server_reactor_id ?? "—"}</td>
        <td>${s.ph != null ? s.ph.toFixed(2) : "—"}</td>
        <td>${s.temperature_c != null ? s.temperature_c.toFixed(1) : "—"}</td>
        <td class="mono">${escapeHtml(spec)}</td>
        <td>${s.error ? escapeHtml(s.error) : "ok"}</td>
      `;
      body.appendChild(tr);
    }
    showErr($("liveError"), "");
  } catch (e) {
    showErr($("liveError"), String(e.message || e));
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
  });
  $("btnStop").addEventListener("click", async () => {
    await api("/api/control/stop", { method: "POST", body: "{}" });
  });

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

  const hasCreds = () =>
    $("api_base_url").value.trim() && $("api_key").value.trim();

  if (hasCreds()) {
    try {
      await loadSites();
      try {
        await syncSensors();
      } catch {
        // ok: user can sync later from Local reactors UI
      }
      if (lastSettings.selected_site_id != null) {
        const want = String(lastSettings.selected_site_id);
        if ($("site_select").querySelector(`option[value="${want}"]`)) {
          $("site_select").value = want;
          await syncReactorsForSite(lastSettings.selected_site_id);
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
  pollLive();
}

init();
