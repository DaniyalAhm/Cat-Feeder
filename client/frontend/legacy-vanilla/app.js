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

let feedDuration = 6;

function renderStatus(s) {
  $("conn").textContent = "connected";
  $("conn").className = "pill ok";
  if (Number.isFinite(Number(s.duration)) && Number(s.duration) > 0) {
    feedDuration = Number(s.duration);
  }
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
let feedLocked = false;
$("btn-feed").onclick = async () => {
  if (feedLocked) { toast("Wait for the feed to finish plus 1s"); return; }
  const btn = $("btn-feed");
  try { await api("/feed-now", { method: "POST" }); toast("Feed triggered"); refresh(); }
  catch (e) {
    if (/busy/i.test(e.message)) { toast("Feed already running — wait for it to finish"); return; }
    if (/cooldown|429/i.test(e.message)) { toast("Wait 1s after the feed finishes"); return; }
    toast("Feed failed: " + e.message); return;
  }
  // Lock covers the whole feed (~duration) + 1s cooldown after it finishes.
  feedLocked = true;
  btn.disabled = true;
  btn.textContent = "Feeding…";
  setTimeout(() => { btn.textContent = "Wait…"; }, Math.max(0, feedDuration * 1000));
  setTimeout(() => { feedLocked = false; btn.disabled = false; btn.textContent = "Feed now"; }, feedDuration * 1000 + 1000);
};

syncModeRow();
refresh();
setInterval(refresh, 3000);
