(() => {
  "use strict";

  const STORAGE_KEY = "jarvis-api-vault-v1";
  const DB_NAME = "jarvis-api-vault";
  const STORE_NAME = "key-material";
  const KEY_ID = "device-aes-gcm-v1";
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  function bytesToBase64(bytes) {
    let binary = "";
    for (let index = 0; index < bytes.length; index += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
    }
    return btoa(binary);
  }

  function base64ToBytes(value) {
    const binary = atob(String(value || ""));
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  }

  function readEnvelope() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return parsed && parsed.version === 1 && parsed.records && typeof parsed.records === "object"
        ? parsed
        : { version: 1, records: {} };
    } catch {
      return { version: 1, records: {} };
    }
  }

  function writeEnvelope(envelope) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(envelope));
  }

  function openDatabase() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB indisponível neste navegador."));
        return;
      }
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE_NAME)) {
          request.result.createObjectStore(STORE_NAME);
        }
      };
      request.onerror = () => reject(new Error("Não foi possível abrir o cofre local."));
      request.onsuccess = () => resolve(request.result);
    });
  }

  async function deviceKey() {
    if (!window.crypto?.subtle || !window.isSecureContext) {
      throw new Error("O cofre exige HTTPS ou localhost para usar criptografia do navegador.");
    }
    const database = await openDatabase();
    try {
      const existing = await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE_NAME, "readonly");
        const request = transaction.objectStore(STORE_NAME).get(KEY_ID);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(new Error("Não foi possível ler a chave do dispositivo."));
      });
      if (existing) return existing;
      const generated = await crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"],
      );
      await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE_NAME, "readwrite");
        transaction.objectStore(STORE_NAME).put(generated, KEY_ID);
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(new Error("Não foi possível proteger a chave do dispositivo."));
      });
      return generated;
    } finally {
      database.close();
    }
  }

  async function seal(value) {
    const key = await deviceKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      key,
      encoder.encode(JSON.stringify(value)),
    );
    return {
      iv: bytesToBase64(iv),
      ciphertext: bytesToBase64(new Uint8Array(ciphertext)),
    };
  }

  async function unseal(record) {
    const key = await deviceKey();
    const plaintext = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: base64ToBytes(record.iv) },
      key,
      base64ToBytes(record.ciphertext),
    );
    return JSON.parse(decoder.decode(plaintext));
  }

  const vault = {
    async save(provider, config) {
      const id = String(provider || "").trim().toLowerCase();
      if (!id) throw new Error("Provedor inválido.");
      const envelope = readEnvelope();
      envelope.records[id] = {
        ...(await seal(config)),
        updatedAt: new Date().toISOString(),
      };
      writeEnvelope(envelope);
      return { provider: id, updatedAt: envelope.records[id].updatedAt };
    },

    async get(provider) {
      const record = readEnvelope().records[String(provider || "").trim().toLowerCase()];
      if (!record) return null;
      try {
        return await unseal(record);
      } catch {
        throw new Error("Este segredo não pode ser aberto neste dispositivo. Remova e salve novamente.");
      }
    },

    list() {
      const records = readEnvelope().records;
      return Object.entries(records).map(([provider, record]) => ({
        provider,
        updatedAt: record.updatedAt || "",
      }));
    },

    remove(provider) {
      const id = String(provider || "").trim().toLowerCase();
      const envelope = readEnvelope();
      const existed = Boolean(envelope.records[id]);
      delete envelope.records[id];
      writeEnvelope(envelope);
      return existed;
    },

    configured(provider) {
      return Boolean(readEnvelope().records[String(provider || "").trim().toLowerCase()]);
    },
  };

  Object.freeze(vault);
  window.JarvisApiVault = vault;
})();
