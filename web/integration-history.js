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
    const history = [{ provider, action, ok: Boolean(data?.ok), message, at: new Date().toISOString() }, ...rows()].slice(0, MAX_ROWS);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(history)); } catch { /* histórico opcional */ }
    render();
  }

  function clear() {
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* histórico opcional */ }
    render();
  }

  return Object.freeze({ clear, record, render });
})();
