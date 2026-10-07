import assert from "node:assert/strict";
import test from "node:test";

import worker, { deviceIdForToken } from "../src/index.js";


class MemoryKv {
  constructor() {
    this.values = new Map();
  }

  async put(key, value) {
    this.values.set(key, value);
  }

  async delete(key) {
    this.values.delete(key);
  }

  async get(key, type) {
    const value = this.values.get(key);
    if (!value) return null;
    return type === "json" ? JSON.parse(value) : value;
  }

  async list({ prefix = "" } = {}) {
    return {
      keys: [...this.values.keys()]
        .filter((key) => key.startsWith(prefix))
        .map((name) => ({ name })),
      list_complete: true,
    };
  }
}

const token = "pairing-token-with-enough-random-characters";

async function request(env, path, init = {}) {
  return worker.fetch(new Request(`https://relay.test${path}`, init), env);
}

test("health endpoint is public", async () => {
  const response = await request({ DEVICES: new MemoryKv() }, "/v1/health");
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ok, true);
});

test("authenticated laptop can publish and phone can resolve", async () => {
  const env = { DEVICES: new MemoryKv() };
  const id = await deviceIdForToken(token);
  const headers = {
    authorization: `Bearer ${token}`,
    "content-type": "application/json",
  };
  const published = await request(env, `/v1/devices/${id}`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ url: "https://aksh.example.test" }),
  });
  assert.equal(published.status, 200);

  const resolved = await request(env, `/v1/devices/${id}`, { headers });
  assert.equal(resolved.status, 200);
  assert.equal((await resolved.json()).url, "https://aksh.example.test");
});

test("wrong token cannot read another device record", async () => {
  const env = { DEVICES: new MemoryKv() };
  const id = await deviceIdForToken(token);
  const response = await request(env, `/v1/devices/${id}`, {
    headers: { authorization: "Bearer another-long-random-pairing-token" },
  });
  assert.equal(response.status, 401);
});

test("relay refuses insecure HTTP target URLs", async () => {
  const env = { DEVICES: new MemoryKv() };
  const id = await deviceIdForToken(token);
  const response = await request(env, `/v1/devices/${id}`, {
    method: "PUT",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ url: "http://192.168.1.2:8765" }),
  });
  assert.equal(response.status, 422);
});

test("relay rejects oversized authenticated writes", async () => {
  const env = { DEVICES: new MemoryKv() };
  const id = await deviceIdForToken(token);
  const response = await request(env, `/v1/devices/${id}`, {
    method: "PUT",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ url: `https://${"a".repeat(3000)}.example.test` }),
  });
  assert.equal(response.status, 413);
});

test("phone can register its fixed B.Tech career briefing profile", async () => {
  const env = { DEVICES: new MemoryKv() };
  const id = await deviceIdForToken(token);
  const response = await request(env, `/v1/devices/${id}/briefing`, {
    method: "PUT",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      enabled: true,
      fcm_token: "firebase-device-token-that-is-long-enough",
      profile: { branch: "all" },
    }),
  });
  assert.equal(response.status, 200);
  const registered = await response.json();
  assert.equal(registered.enabled, true);
  assert.deepEqual(registered.profile.regions, [
    "Uttar Pradesh",
    "Bihar",
    "All India",
  ]);

  const status = await request(env, `/v1/devices/${id}/briefing`, {
    headers: { authorization: `Bearer ${token}` },
  });
  const body = await status.json();
  assert.equal(body.enabled, true);
  assert.equal("fcm_token" in body, false);
});

test("disabling briefing removes the push registration", async () => {
  const env = { DEVICES: new MemoryKv() };
  const id = await deviceIdForToken(token);
  const headers = {
    authorization: `Bearer ${token}`,
    "content-type": "application/json",
  };
  await request(env, `/v1/devices/${id}/briefing`, {
    method: "PUT",
    headers,
    body: JSON.stringify({
      enabled: true,
      fcm_token: "firebase-device-token-that-is-long-enough",
    }),
  });
  const disabled = await request(env, `/v1/devices/${id}/briefing`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ enabled: false }),
  });
  assert.equal(disabled.status, 200);

  const status = await request(env, `/v1/devices/${id}/briefing`, { headers });
  assert.equal((await status.json()).enabled, false);
});
