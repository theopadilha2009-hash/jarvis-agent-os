(() => {
  "use strict";

  const ENDPOINTS = ["http://127.0.0.1:8123", "http://localhost:8123"];
  const TTL_OK = 30_000;
  const TTL_MISS = 4_000;
  let cache = { base: "", at: 0, engine: "", voice: "", ok: false };

  function fetchOpts(init) {
    const opts = Object.assign({ targetAddressSpace: "loopback" }, init || {});
    if (opts.timeoutMs && window.AbortSignal?.timeout) {
      opts.signal = window.AbortSignal.timeout(opts.timeoutMs);
    }
    delete opts.timeoutMs;
    return opts;
  }

  async function probe(force) {
    const ttl = cache.ok ? TTL_OK : TTL_MISS;
    if (!force && cache.at && Date.now() - cache.at < ttl) return cache.ok ? cache.base : "";
    for (const base of ENDPOINTS) {
      try {
        const response = await fetch(`${base}/health`, fetchOpts({ method: "GET", timeoutMs: 600 }));
        if (!response.ok) continue;
        const data = await response.json().catch(() => ({}));
        if (!data.ok) continue;
        cache = {
          base,
          at: Date.now(),
          engine: data.engine || "pocket_tts",
          voice: data.voice || "rafael",
          ultronVoice: data.ultron_voice || "javert",
          ok: true,
        };
        return base;
      } catch {
        /* próximo endpoint */
      }
    }
    cache = { base: "", at: Date.now(), engine: "", voice: "", ok: false };
    return "";
  }

  function activePersona(explicit) {
    const raw = String(explicit || document.documentElement?.dataset?.persona || "jarvis").toLowerCase();
    return raw.indexOf("ultron") >= 0 ? "ultron" : "jarvis";
  }

  async function speakBlob(text, options) {
    const clip = String(text || "").replace(/\s+/g, " ").trim();
    if (!clip) return null;
    const base = await probe();
    if (!base) return null;
    const persona = activePersona(options && options.persona);
    try {
      const response = await fetch(`${base}/speech`, fetchOpts({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clip.slice(0, 2200), persona }),
        timeoutMs: 20_000,
      }));
      if (!response.ok) {
        cache.at = 0;
        return null;
      }
      const blob = await response.blob();
      if (!blob || blob.size < 44) return null;
      return blob;
    } catch {
      cache.at = 0;
      return null;
    }
  }

  window.JarvisLocalVoice = {
    probe,
    speakBlob,
    info: () => Object.assign({}, cache),
  };
})();
