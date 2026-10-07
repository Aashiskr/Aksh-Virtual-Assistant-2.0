import {
  buildCareerBriefing,
  notificationForBriefing,
} from "./briefing.js";
import {
  hasFirebaseConfiguration,
  sendCareerNotification,
} from "./fcm.js";

const DEVICE_ID_PATTERN = /^[a-f0-9]{24}$/;
const RECORD_TTL_SECONDS = 14 * 24 * 60 * 60;
const BRIEFING_TTL_SECONDS = 120 * 24 * 60 * 60;
const MAX_BODY_BYTES = 8192;
const MAX_TUNNEL_BODY_BYTES = 2048;
const BRIEFING_PREFIX = "briefing:";
const LATEST_PREFIX = "briefing-latest:";

export async function deviceIdForToken(token) {
  const bytes = new TextEncoder().encode(token);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 24);
}

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function bearerToken(request) {
  const authorization = request.headers.get("authorization") || "";
  return authorization.toLowerCase().startsWith("bearer ")
    ? authorization.slice(7).trim()
    : "";
}

async function authorize(request, deviceId) {
  const token = bearerToken(request);
  if (token.length < 24) return false;
  return (await deviceIdForToken(token)) === deviceId;
}

function validTunnelUrl(value) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

async function jsonBody(request, maximumBytes = MAX_BODY_BYTES) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > maximumBytes) {
    throw new HttpError(413, "Request body is too large");
  }
  const rawBody = await request.text();
  if (new TextEncoder().encode(rawBody).byteLength > maximumBytes) {
    throw new HttpError(413, "Request body is too large");
  }
  try {
    return JSON.parse(rawBody || "{}");
  } catch {
    throw new HttpError(400, "Invalid JSON");
  }
}

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function safeBriefingRegistration(body) {
  const enabled = body?.enabled === true;
  if (!enabled) return { enabled: false };
  const fcmToken = String(body?.fcm_token || "").trim();
  if (fcmToken.length < 20 || fcmToken.length > 4096) {
    throw new HttpError(422, "A valid Firebase device token is required");
  }
  return {
    enabled: true,
    fcm_token: fcmToken,
    profile: {
      course: "B.Tech",
      year: 4,
      branch: String(body?.profile?.branch || "all").slice(0, 40),
      regions: ["Uttar Pradesh", "Bihar", "All India"],
      timezone: "Asia/Kolkata",
      delivery_hour: 11,
    },
    updated_at: new Date().toISOString(),
  };
}

async function handleBriefing(request, env, deviceId, action) {
  const key = `${BRIEFING_PREFIX}${deviceId}`;
  if (action === "latest" && request.method === "GET") {
    const latest = await env.DEVICES.get(`${LATEST_PREFIX}${deviceId}`, "json");
    return latest
      ? json(latest)
      : json({ detail: "No career briefing has been generated yet" }, 404);
  }
  if (action === "test" && request.method === "POST") {
    const registration = await env.DEVICES.get(key, "json");
    if (!registration?.enabled) {
      return json({ detail: "Daily career briefing is not enabled" }, 409);
    }
    const briefing = await buildCareerBriefing(env, registration.profile);
    await storeLatestBriefing(env, deviceId, briefing);
    let notificationSent = false;
    let warning = "";
    if (hasFirebaseConfiguration(env)) {
      await sendCareerNotification(
        env,
        registration.fcm_token,
        briefing,
        notificationForBriefing(briefing),
      );
      notificationSent = true;
    } else {
      warning = "Firebase Worker secrets are not configured";
    }
    return json({
      ok: true,
      notification_sent: notificationSent,
      warning,
      briefing,
    });
  }
  if (action) return json({ detail: "Method not allowed" }, 405);

  if (request.method === "PUT") {
    const registration = safeBriefingRegistration(await jsonBody(request));
    if (!registration.enabled) {
      await env.DEVICES.delete(key);
      return json({ ok: true, enabled: false });
    }
    await env.DEVICES.put(key, JSON.stringify(registration), {
      expirationTtl: BRIEFING_TTL_SECONDS,
    });
    return json({
      ok: true,
      enabled: true,
      schedule: "daily at 11:00 Asia/Kolkata",
      profile: registration.profile,
    });
  }
  if (request.method === "GET") {
    const registration = await env.DEVICES.get(key, "json");
    return registration
      ? json({
        enabled: registration.enabled,
        schedule: "daily at 11:00 Asia/Kolkata",
        profile: registration.profile,
        updated_at: registration.updated_at,
      })
      : json({ enabled: false });
  }
  return json({ detail: "Method not allowed" }, 405);
}

async function storeLatestBriefing(env, deviceId, briefing) {
  await env.DEVICES.put(
    `${LATEST_PREFIX}${deviceId}`,
    JSON.stringify(briefing),
    { expirationTtl: BRIEFING_TTL_SECONDS },
  );
}

export async function runDailyCareerBriefings(env) {
  const profileCache = new Map();
  let cursor;
  let delivered = 0;
  let failed = 0;
  do {
    const page = await env.DEVICES.list({ prefix: BRIEFING_PREFIX, cursor });
    for (const item of page.keys) {
      const registration = await env.DEVICES.get(item.name, "json");
      if (!registration?.enabled) continue;
      const deviceId = item.name.slice(BRIEFING_PREFIX.length);
      try {
        const profileKey = JSON.stringify(registration.profile);
        let briefing = profileCache.get(profileKey);
        if (!briefing) {
          briefing = await buildCareerBriefing(env, registration.profile);
          profileCache.set(profileKey, briefing);
        }
        await storeLatestBriefing(env, deviceId, briefing);
        await sendCareerNotification(
          env,
          registration.fcm_token,
          briefing,
          notificationForBriefing(briefing),
        );
        delivered += 1;
      } catch (error) {
        failed += 1;
        console.error(`Career briefing failed for ${deviceId}:`, error);
      }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return { delivered, failed };
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (request.method === "GET" && url.pathname === "/v1/health") {
        return json({
          ok: true,
          service: "aksh-device-relay",
          career_briefing: true,
        });
      }

      const briefingMatch = url.pathname.match(
        /^\/v1\/devices\/([a-f0-9]{24})\/briefing(?:\/(latest|test))?$/,
      );
      if (briefingMatch) {
        const deviceId = briefingMatch[1];
        if (!(await authorize(request, deviceId))) {
          return json({ detail: "Invalid device credentials" }, 401);
        }
        return handleBriefing(request, env, deviceId, briefingMatch[2]);
      }

      const match = url.pathname.match(/^\/v1\/devices\/([a-f0-9]{24})$/);
      if (!match || !DEVICE_ID_PATTERN.test(match[1])) {
        return json({ detail: "Not found" }, 404);
      }
      const deviceId = match[1];
      if (!(await authorize(request, deviceId))) {
        return json({ detail: "Invalid device credentials" }, 401);
      }

      if (request.method === "PUT") {
        const body = await jsonBody(request, MAX_TUNNEL_BODY_BYTES);
        if (!validTunnelUrl(body?.url)) {
          return json({ detail: "A valid HTTPS URL is required" }, 422);
        }
        const record = {
          url: body.url,
          updated_at: new Date().toISOString(),
        };
        await env.DEVICES.put(deviceId, JSON.stringify(record), {
          expirationTtl: RECORD_TTL_SECONDS,
        });
        return json({ ok: true, device_id: deviceId });
      }

      if (request.method === "GET") {
        const record = await env.DEVICES.get(deviceId, "json");
        return record
          ? json({ device_id: deviceId, ...record })
          : json({ detail: "Laptop is offline or not registered yet" }, 404);
      }
      return json({ detail: "Method not allowed" }, 405);
    } catch (error) {
      if (error instanceof HttpError) {
        return json({ detail: error.message }, error.status);
      }
      console.error("Aksh relay request failed:", error);
      return json({ detail: "Relay request failed" }, 500);
    }
  },

  async scheduled(controller, env, ctx) {
    ctx.waitUntil(runDailyCareerBriefings(env));
  },
};
