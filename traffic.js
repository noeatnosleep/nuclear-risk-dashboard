(function(){
  const STORE_KEY = "nrd_traffic_v1";
  const SESSION_KEY = "nrd_traffic_session_v1";

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
  function inc(map, key, by=1){ map[key] = Number(map[key]||0) + by; }

  function collectUtm(){
    const params = new URLSearchParams(location.search || "");
    const fields = ["utm_source","utm_medium","utm_campaign","utm_term","utm_content"];
    const pairs = [];
    fields.forEach((f)=>{ const v=params.get(f); if(v) pairs.push(`${f}=${v}`); });
    return pairs;
  }

  function startSession(){
    const startedAt = Date.now();
    const session = { id: `${startedAt}-${Math.random().toString(36).slice(2,9)}`, started_at_ms: startedAt, path: pathKey(), closed: false };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    return session;
  }

  function readSession(){
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || "null"); } catch (_) { return null; }
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
  }

  function trackPage(){
    const data = read();
    const p = pathKey();
    if (!data.paths[p]) data.paths[p] = { views: 0, sessions: 0, total_dwell_ms: 0 };

    data.totals.views += 1;
    data.totals.sessions += 1;
    data.paths[p].views += 1;
    data.paths[p].sessions += 1;

    inc(data.referrers, refDomain(), 1);
    collectUtm().forEach((k)=>inc(data.utm, k, 1));
    inc(data.devices, deviceClass(), 1);
    inc(data.nav_types, navType(), 1);

    data.visits.unshift({ ts: nowIso(), path: p, referrer: refDomain(), nav_type: navType(), device: deviceClass() });
    data.visits = data.visits.slice(0, 120);
    write(data);

    startSession();

    window.addEventListener("pagehide", closeSession, { once: true });
    document.addEventListener("visibilitychange", function(){ if (document.visibilityState === "hidden") closeSession(); }, { once: true });
  }

  function clearAll(){
    localStorage.removeItem(STORE_KEY);
    localStorage.removeItem(SESSION_KEY);
  }

  window.NRDTraffic = { trackPage, closeSession, clearAll, read, STORE_KEY };
})();
