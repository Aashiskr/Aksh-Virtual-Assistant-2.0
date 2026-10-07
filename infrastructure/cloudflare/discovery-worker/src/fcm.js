const FIREBASE_SCOPE = "https://www.googleapis.com/auth/firebase.messaging";
let cachedAccessToken = null;

export function hasFirebaseConfiguration(env) {
  return Boolean(
    env.FIREBASE_PROJECT_ID
    && env.FIREBASE_CLIENT_EMAIL
    && env.FIREBASE_PRIVATE_KEY,
  );
}

export function fcmMessage(token, briefing, notification) {
  return {
    message: {
      token,
      data: {
        type: "career_briefing",
        briefing_id: briefing.id,
        title: notification.title,
        body: notification.body,
      },
      android: {
        priority: "high",
        ttl: "86400s",
      },
    },
  };
}

export async function sendCareerNotification(
  env,
  fcmToken,
  briefing,
  notification,
) {
  if (!hasFirebaseConfiguration(env)) {
    throw new Error("Firebase Worker secrets are not configured");
  }
  const accessToken = await firebaseAccessToken(env);
  const endpoint = `https://fcm.googleapis.com/v1/projects/${encodeURIComponent(env.FIREBASE_PROJECT_ID)}/messages:send`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      authorization: `Bearer ${accessToken}`,
      "content-type": "application/json; charset=utf-8",
    },
    body: JSON.stringify(fcmMessage(fcmToken, briefing, notification)),
  });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`FCM returned HTTP ${response.status}: ${body.slice(0, 300)}`);
  }
  return body ? JSON.parse(body) : {};
}

async function firebaseAccessToken(env) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  if (cachedAccessToken && cachedAccessToken.expiresAt > nowSeconds + 60) {
    return cachedAccessToken.value;
  }
  const assertion = await serviceAccountAssertion(env, nowSeconds);
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
  });
  const body = await response.json();
  if (!response.ok || !body.access_token) {
    throw new Error(`Firebase OAuth failed with HTTP ${response.status}`);
  }
  cachedAccessToken = {
    value: body.access_token,
    expiresAt: nowSeconds + Number(body.expires_in || 3600),
  };
  return cachedAccessToken.value;
}

async function serviceAccountAssertion(env, issuedAt) {
  const header = base64UrlJson({ alg: "RS256", typ: "JWT" });
  const claims = base64UrlJson({
    iss: env.FIREBASE_CLIENT_EMAIL,
    scope: FIREBASE_SCOPE,
    aud: "https://oauth2.googleapis.com/token",
    iat: issuedAt,
    exp: issuedAt + 3600,
  });
  const unsigned = `${header}.${claims}`;
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemBytes(env.FIREBASE_PRIVATE_KEY),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(unsigned),
  );
  return `${unsigned}.${base64UrlBytes(new Uint8Array(signature))}`;
}

function pemBytes(value) {
  const normalized = String(value)
    .replace(/\\n/g, "\n")
    .replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g, "");
  const binary = atob(normalized);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function base64UrlJson(value) {
  return base64UrlBytes(new TextEncoder().encode(JSON.stringify(value)));
}

function base64UrlBytes(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}
