"use strict";

document.getElementById("memoryExplorerButton")?.addEventListener("click", () => {
  import("/ui/memory-explorer.js?v=20260813-memory1").catch(() => null);
}, { once: true });
