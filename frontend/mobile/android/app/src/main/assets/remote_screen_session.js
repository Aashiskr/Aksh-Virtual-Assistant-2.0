(() => {
  "use strict";

  const REQUEST_TIMEOUT_MS = 15000;

  function notifySessionChanged(bridge, sessionId) {
    if (
      bridge
      && typeof bridge.updateScreenSession === "function"
      && typeof sessionId === "string"
      && sessionId.trim()
    ) {
      bridge.updateScreenSession(sessionId);
      return true;
    }
    return false;
  }

  function create({config, setStatus}) {
    let sessionId = config.sessionId;
    let renewingSession = null;

    const headers = (json = false, includeSession = true) => ({
      "Authorization": `Bearer ${config.token}`,
      ...(includeSession ? {"X-Aksh-Screen-Session": sessionId} : {}),
      ...(json ? {"Content-Type": "application/json"} : {})
    });

    async function fetchTimed(path, options = {}, includeSession = true) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      try {
        return await fetch(`${config.baseUrl}${path}`, {
          ...options,
          cache: "no-store",
          headers: {
            ...headers(Boolean(options.body), includeSession),
            ...(options.headers || {})
          },
          signal: controller.signal
        });
      } finally {
        clearTimeout(timer);
      }
    }

    async function renew() {
      if (renewingSession) return renewingSession;
      renewingSession = (async () => {
        setStatus("RESTORING SESSION");
        const response = await fetchTimed(
          "/v1/screen/sessions",
          {method: "POST", body: "{}"},
          false
        );
        if (!response.ok) throw new Error(`Session HTTP ${response.status}`);
        const payload = await response.json();
        if (!payload.session_id) throw new Error("Session response invalid");
        sessionId = payload.session_id;
        notifySessionChanged(
          typeof AkshBridge === "undefined" ? null : AkshBridge,
          sessionId
        );
      })();
      try {
        await renewingSession;
      } finally {
        renewingSession = null;
      }
    }

    async function request(path, options = {}, allowRenewal = true) {
      let response = await fetchTimed(path, options);
      if (response.status === 401 && allowRenewal) {
        await renew();
        response = await fetchTimed(path, options);
      }
      return response;
    }

    return {request};
  }

  window.AkshRemoteSession = {create, notifySessionChanged};
})();
