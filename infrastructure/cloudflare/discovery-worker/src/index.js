const DEVICE_ID_PATTERN = /^[a-f0-9]{24}$/;
const RECORD_TTL_SECONDS = 14 * 24 * 60 * 60;
const MAX_BODY_BYTES = 2048;

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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/v1/health") {
      return json({ ok: true, service: "aksh-device-relay" });
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
      const declaredLength = Number(request.headers.get("content-length") || 0);
      if (declaredLength > MAX_BODY_BYTES) {
        return json({ detail: "Request body is too large" }, 413);
      }
      const rawBody = await request.text();
      if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
        return json({ detail: "Request body is too large" }, 413);
      }
      let body;
      try {
        body = JSON.parse(rawBody);
      } catch {
        return json({ detail: "Invalid JSON" }, 400);
      }
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
  },
};
