// Talks to the backend API (default :6607 on the same host).
const API = `http://${location.hostname}:6607/api`;

const $ = (id) => document.getElementById(id);
const toast = (msg) => {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._h);
  toast._h = setTimeout(() => (t.hidden = true), 3000);
};

async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}

function renderStatus(s) {
  $("conn").textContent = "connected";
  $("conn").className = "pill ok";
  $("st-running").textContent = s.running ? "▶ running" : "⏸ stopped";
  $("st-next").textContent = s.next;
  $("st-last").textContent = s.last;
  $("st-motor").textContent =
    s.esp == null ? "unreachable" : s.esp.motor_running ? "ON" : "off";
  $("st-target").textContent = `${s.ip}:${s.port}`;
  $("st-plan").textContent =
    s.mode === "interval" ? `every ${s.interval}s × ${s.duration}s` : s.times.join(", ");
  if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "SELECT") {
    $("cfg-ip").value = s.ip;
    $("cfg-port").value = s.port;
    $("cfg-times").value = s.times.join(",");
    $("cfg-interval").value = s.interval;
    $("cfg-duration").value = s.duration;
    $("cfg-mode").value = s.mode;
    syncModeRow();
  }
}

async function renderEvents() {
  try {
    const { events } = await api("/events");
    $("events").textContent = events.length ? events.join("\n") : "–";
  } catch { /* keep old */ }
}

async function refresh() {
  try {
    renderStatus(await api("/status"));
    await renderEvents();
  } catch {
    $("conn").textContent = "backend unreachable";
    $("conn").className = "pill bad";
  }
}

function syncModeRow() {
  const interval = $("cfg-mode").value === "interval";
  $("row-times").hidden = interval;
  $("row-interval").hidden = !interval;
}

async function save() {
  try {
    await api("/config", {
      method: "POST",
      body: JSON.stringify({
        ip: $("cfg-ip").value.trim(),
        port: Number($("cfg-port").value),
        mode: $("cfg-mode").value,
        times: $("cfg-times").value,
        interval: Number($("cfg-interval").value),
        duration: Number($("cfg-duration").value),
      }),
    });
    toast("Saved");
    refresh();
  } catch (e) {
    toast("Save failed: " + e.message);
  }
}

$("btn-save").onclick = save;
$("cfg-mode").onchange = syncModeRow;
$("btn-start").onclick = async () => {
  try { await api("/start", { method: "POST" }); toast("Scheduler started"); refresh(); }
  catch (e) { toast("Start failed: " + e.message); }
};
$("btn-stop").onclick = async () => {
  try { await api("/stop", { method: "POST" }); toast("Scheduler stopped"); refresh(); }
  catch (e) { toast("Stop failed: " + e.message); }
};
$("btn-feed").onclick = async () => {
  try { await api("/feed-now", { method: "POST" }); toast("Feed triggered"); refresh(); }
  catch (e) { toast("Feed failed: " + e.message); }
};

syncModeRow();
refresh();
setInterval(refresh, 3000);
