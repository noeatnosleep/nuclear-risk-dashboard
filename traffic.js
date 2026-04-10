(function(){
  const STORE_KEY = "nrd_traffic_v2";
  const SESSION_KEY = "nrd_traffic_session_v2";
  const GLOBAL_NS = "nuclear-risk-dashboard-global";
  const GLOBAL_API = "https://api.countapi.xyz";

  function nowIso(){ return new Date().toISOString(); }
  function pathKey(){ return location.pathname || "/"; }
  function refDomain(){
    try {
      if (!document.referrer) return "direct";
      return new URL(document.referrer).hostname || "direct";
    } catch (_) {
      return "unknown";
    }
  }
  function deviceClass(){ return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent||"") ? "mobile" : "desktop"; }
  function navType(){
    const e = performance.getEntriesByType && performance.getEntriesByType("navigation");
    if (Array.isArray(e) && e[0] && e[0].type) return e[0].type;
    return "unknown";
  }
  function sanitizeKey(v){ return String(v||"na").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 64) || "na"; }

  function empty(){
    return {
      first_seen: nowIso(),
      last_seen: nowIso(),
      totals: { views: 0, sessions: 0, total_dwell_ms: 0 },
      paths: {},
      referrers: {},
      utm: {},
      devices: { desktop: 0, mobile: 0 },
      nav_types: {},
      visits: []
    };
  }

  function read(){
    try {
      const raw = localStorage.getItem(STORE_KEY);
      return raw ? JSON.parse(raw) : empty();
    } catch (_) {
      return empty();
    }
  }

  function write(data){
    data.last_seen = nowIso();
    localStorage.setItem(STORE_KEY, JSON.stringify(data));
  }

  function inc(map, key, by){
    const n = Number(by === undefined ? 1 : by);
    map[key] = Number(map[key] || 0) + n;
  }

  function collectUtm(){
    const params = new URLSearchParams(location.search || "");
    const fields = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
    const pairs = [];
    fields.forEach((f)=>{
      const v=params.get(f);
      if(v) pairs.push(`${f}=${v}`);
    });
    return pairs;
  }

  function startSession(){
    const startedAt = Date.now();
    const session = {
      id: `${startedAt}-${Math.random().toString(36).slice(2,9)}`,
      started_at_ms: startedAt,
      path: pathKey(),
      closed: false
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    return session;
  }

  function readSession(){
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || "null"); } catch (_) { return null; }
  }

  function countApiHit(key, amount){
    const safeKey = sanitizeKey(key);
    const url = amount === undefined
      ? `${GLOBAL_API}/hit/${encodeURIComponent(GLOBAL_NS)}/${encodeURIComponent(safeKey)}`
      : `${GLOBAL_API}/update/${encodeURIComponent(GLOBAL_NS)}/${encodeURIComponent(safeKey)}?amount=${encodeURIComponent(String(amount))}`;
    return fetch(url, { method: "GET", mode: "cors", keepalive: true }).catch(()=>null);
  }

  function globalTrackVisit(path, ref, device, nav){
    const safePath = sanitizeKey(path === "/" ? "home" : path.replace(/^\//, ""));
    countApiHit("views_total");
    countApiHit(`path_${safePath}`);
    countApiHit(`ref_${sanitizeKey(ref)}`);
    countApiHit(`device_${sanitizeKey(device)}`);
    countApiHit(`nav_${sanitizeKey(nav)}`);
  }

  function globalTrackSessionClose(path, dwellMs){
    const safePath = sanitizeKey(path === "/" ? "home" : path.replace(/^\//, ""));
    const dwellSec = Math.max(0, Math.round(Number(dwellMs || 0) / 1000));
    countApiHit("sessions_closed");
    countApiHit(`session_path_${safePath}`);
    if (dwellSec > 0) {
      countApiHit("dwell_total_seconds", dwellSec);
      countApiHit(`dwell_path_${safePath}_seconds`, dwellSec);
    }
  }

  function closeSession(){
    const session = readSession();
    if (!session || session.closed) return;
    session.closed = true;
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));

    const dwell = Math.max(0, Date.now() - Number(session.started_at_ms || Date.now()));
    const data = read();
    data.totals.total_dwell_ms += dwell;
    if (!data.paths[session.path]) data.paths[session.path] = { views: 0, sessions: 0, total_dwell_ms: 0 };
    data.paths[session.path].total_dwell_ms += dwell;
    write(data);

    globalTrackSessionClose(session.path, dwell);
  }

  function trackPage(){
    const data = read();
    const p = pathKey();
    if (!data.paths[p]) data.paths[p] = { views: 0, sessions: 0, total_dwell_ms: 0 };

    const ref = refDomain();
    const device = deviceClass();
    const nav = navType();

    data.totals.views += 1;
    data.totals.sessions += 1;
    data.paths[p].views += 1;
    data.paths[p].sessions += 1;

    inc(data.referrers, ref, 1);
    collectUtm().forEach((k)=>inc(data.utm, k, 1));
    inc(data.devices, device, 1);
    inc(data.nav_types, nav, 1);

    data.visits.unshift({ ts: nowIso(), path: p, referrer: ref, nav_type: nav, device: device });
    data.visits = data.visits.slice(0, 120);
    write(data);

    globalTrackVisit(p, ref, device, nav);

    startSession();
    window.addEventListener("pagehide", closeSession, { once: true });
    document.addEventListener("visibilitychange", function(){ if (document.visibilityState === "hidden") closeSession(); }, { once: true });
  }

  function clearAll(){
    localStorage.removeItem(STORE_KEY);
    localStorage.removeItem(SESSION_KEY);
  }

  function globalGet(key){
    const safeKey = sanitizeKey(key);
    const url = `${GLOBAL_API}/get/${encodeURIComponent(GLOBAL_NS)}/${encodeURIComponent(safeKey)}`;
    return fetch(url, { method: "GET", mode: "cors" })
      .then(r=>r.ok ? r.json() : null)
      .then(j=>j && typeof j.value === "number" ? j.value : 0)
      .catch(()=>0);
  }

  window.NRDTraffic = { trackPage, closeSession, clearAll, read, globalGet, STORE_KEY, GLOBAL_NS };
})();
