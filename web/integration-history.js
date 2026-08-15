"use strict";

window.JarvisIntegrationHistory = (() => {
  const STORAGE_KEY = "jarvis-integration-history-v1";
  const MAX_ROWS = 30;

  function rows() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(value) ? value.slice(0, MAX_ROWS) : [];
    } catch {
      return [];
    }
  }

  function render() {
    const target = document.getElementById("integrationHistoryList");
    if (!target) return;
    const history = rows();
    target.replaceChildren();
    if (!history.length) {
      const empty = document.createElement("small");
      empty.textContent = "Nenhuma operação registrada neste dispositivo.";
      target.appendChild(empty);
      return;
    }
    history.forEach((row) => {
      const item = document.createElement("article");
      item.className = "integration-history-row";
      item.dataset.ok = String(Boolean(row.ok));
      const dot = document.createElement("i");
      const copy = document.createElement("span");
      const title = document.createElement("b");
      title.textContent = `${String(row.provider || "API").toUpperCase()} · ${row.action || "operação"}`;
      const detail = document.createElement("small");
      detail.textContent = row.message || (row.ok ? "concluída" : "falhou");
      copy.append(title, detail);
      const time = document.createElement("time");
      time.dateTime = row.at || "";
      time.textContent = row.at
        ? new Date(row.at).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
        : "agora";
      item.append(dot, copy, time);
      target.appendChild(item);
    });
  }

  function record(provider, action, data) {
    const message = String(data?.message || data?.error || (data?.ok ? "concluída" : "falhou"))
      .replace(/(?:sk-[A-Za-z0-9_-]+|github_pat_[A-Za-z0-9_]+|Bearer\s+\S+)/gi, "[protegido]")
      .slice(0, 160);
    const latency = Number(data?.latency_ms);
    const quota = String(data?.quota || "").slice(0, 100);
    const history = [{
      provider,
      action,
      ok: Boolean(data?.ok),
      message,
      at: new Date().toISOString(),
      ...(Number.isFinite(latency) ? { latency_ms: Math.max(0, Math.min(latency, 120_000)) } : {}),
      ...(quota ? { quota } : {}),
    }, ...rows()].slice(0, MAX_ROWS);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(history)); } catch { /* histórico opcional */ }
    render();
    window.dispatchEvent(new Event("jarvis-integration-activity"));
  }

  function clear() {
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* histórico opcional */ }
    render();
    window.dispatchEvent(new Event("jarvis-integration-activity"));
  }

  function summary(provider) {
    const providerRows = rows().filter((row) => row.provider === provider);
    const latest = providerRows[0] || {};
    const measured = providerRows.find((row) => Number.isFinite(Number(row.latency_ms))) || {};
    const metered = providerRows.find((row) => row.quota) || {};
    const failure = providerRows.find((row) => row.ok === false);
    return {
      ok: latest.ok,
      at: latest.at || "",
      latency_ms: measured.latency_ms,
      quota: metered.quota || "",
      last_failure: failure?.message || "",
    };
  }

  document.querySelector('[data-integration-tab="health"]')?.addEventListener("click", () => {
    import("/ui/integration-health.js?v=20260813-ultronfix1").catch(() => null);
  }, { once: true });
  document.getElementById("voiceTuningButton")?.addEventListener("click", () => {
    import("/ui/voice-calibrator.js?v=20260815-vozes2").catch(() => null);
  }, { once: true });
  document.getElementById("personaPanelButton")?.addEventListener("click", () => {
    import("/ui/persona-panel.js?v=20260815-persona1")
      .then(() => window.JarvisPersonaPanel?.open())
      .catch(() => null);
  });
  document.querySelector('[data-integration-tab="workflows"]')?.addEventListener("click", () => {
    import("/ui/n8n-template-pack.js?v=20260813-ultronfix1").catch(() => null);
  }, { once: true });

  return Object.freeze({ clear, record, render, summary });
})();
