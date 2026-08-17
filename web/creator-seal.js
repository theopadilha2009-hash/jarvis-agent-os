(() => {
  "use strict";
  const MARK = "VGhlbyBMb3JlbnR6IFBhZGlsaGE=";
  const KEY_HEX = "d668fc02b10d1ea9533108b1c48e02f2e83ad3712e1aa99ee6fd0f081588fa00";
  const CIPHER = "ggCZbZFBcds2X3zL5N5jloFWuxA=";
  const EXPECT = { n: 20, a: 84, z: 97, s: 113 };

  function keyBytes() {
    const out = new Uint8Array(32);
    for (let i = 0; i < 32; i += 1) out[i] = parseInt(KEY_HEX.slice(i * 2, i * 2 + 2), 16);
    return out;
  }

  function decode() {
    const key = keyBytes();
    const raw = Uint8Array.from(atob(CIPHER), (char) => char.charCodeAt(0));
    let name = "";
    for (let i = 0; i < raw.length; i += 1) name += String.fromCharCode(raw[i] ^ key[i % key.length]);
    let sum = 0;
    for (let i = 0; i < name.length; i += 1) sum = (sum + name.charCodeAt(i)) & 255;
    if (name.length !== EXPECT.n || name.charCodeAt(0) !== EXPECT.a || name.charCodeAt(name.length - 1) !== EXPECT.z || sum !== EXPECT.s) {
      return atob(MARK);
    }
    return name;
  }

  function creatorName() {
    try { return decode(); } catch { return atob(MARK); }
  }

  let painting = false;
  function paint() {
    if (painting) return;
    painting = true;
    try {
      const name = creatorName();
      const first = name.split(" ")[0];
      const link = document.getElementById("identityCreator");
      if (link && !String(link.textContent || "").includes(first)) {
        const prefix = document.documentElement.dataset.persona === "ultron" ? "para " : "por ";
        link.textContent = prefix + name;
        if (!link.getAttribute("href")) link.setAttribute("href", "/theo");
      }
      const title = document.title || "";
      if (title && !title.includes(first)) document.title = `${title.split("·")[0].trim()} · ${name}`;
      document.querySelectorAll("[data-creator-lock]").forEach((node) => {
        if (!String(node.textContent || "").includes(first)) node.textContent = name;
      });
    } finally {
      painting = false;
    }
  }

  const api = {
    name: creatorName,
    lock: paint,
    mark: MARK,
  };
  window.JarvisCreator = api;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", paint, { once: true });
  else paint();
  const observer = new MutationObserver(paint);
  const start = () => {
    const target = document.getElementById("identityCreator") || document.body;
    if (target) observer.observe(target, { childList: true, characterData: true, subtree: true });
  };
  if (document.body) start();
  else document.addEventListener("DOMContentLoaded", start, { once: true });
})();
