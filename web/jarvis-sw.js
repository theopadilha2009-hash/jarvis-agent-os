"use strict";

const CACHE_VERSION = "jarvis-mobile-shell-20260818-voice1";
const SHELL = [
  "/",
  "/ui/manifest.webmanifest?v=20260813-apitools1",
  "/ui/jarvis-logo.png?v=20260813-logonative1",
  "/ui/jarvis.css?v=20260817-move1",
  "/ui/ui-repair.css?v=20260815-vozes2",
  "/ui/api-panel.css?v=20260813-ultronfix1",
  "/ui/integration-health.css?v=20260813-ultronfix1",
  "/ui/voice-calibrator.css?v=20260815-vozes2",
  "/ui/memory-explorer.css?v=20260813-ultronfix1",
  "/ui/action-permissions.css?v=20260813-ultronfix1",
  "/ui/ultron-completion.css?v=20260815-vozes2",
  "/ui/responsive-polish.css?v=20260815-vozes2",
  "/ui/shell.css?v=20260817-move1",
  "/ui/api-vault.js?v=20260813-ultronfix1",
  "/ui/integration-history.js?v=20260813-ultronfix1",
  "/ui/feature-loader.js?v=20260815-vozes2",
  "/ui/presence-loader.js?v=20260813-ultronfix1",
  "/ui/integration-health.js?v=20260813-ultronfix1",
  "/ui/voice-calibrator.js?v=20260815-vozes2",
  "/ui/n8n-template-pack.js?v=20260813-ultronfix1",
  "/ui/memory-explorer.js?v=20260813-ultronfix1",
  "/ui/action-permissions.js?v=20260813-ultronfix1",
  "/ui/voice-pacing.js?v=20260813-voice2",
  "/ui/device-feedback.js?v=20260813-device1",
  "/ui/jarvis.js?v=20260818-voice1",
  "/ui/local-voice.js?v=20260818-voice1",
  "/ui/creator-seal.js?v=20260817-app1",
  "/ui/jarvis-3d.js?v=20260815-vozes2",
  "/ui/aurora.js?v=20260813-apitools1",
  "/ui/strands.js?v=20260813-apitools1",
  "/ui/vendor/ogl/jarvis.js",
  "/ui/vendor/three.module.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((name) => name.startsWith("jarvis-mobile-shell-") && name !== CACHE_VERSION).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(request) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(request, { signal: controller.signal });
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return (await caches.match(request, { ignoreSearch: true })) || (await caches.match("/", { ignoreSearch: true }));
  } finally {
    clearTimeout(timeout);
  }
}

async function staticAsset(request) {
  const cached = await caches.match(request, { ignoreSearch: true });
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      await cache.put(request, response.clone());
    }
    return response;
  } catch {
    return Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request));
    return;
  }
  if (url.pathname.startsWith("/ui/") || url.pathname.startsWith("/asset/")) {
    event.respondWith(staticAsset(request));
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destination = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
      if (existing) return existing.focus();
      return self.clients.openWindow(destination);
    })
  );
});
