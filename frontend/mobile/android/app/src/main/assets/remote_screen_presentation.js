(function (root) {
  "use strict";

  const ACTIONS = Object.freeze([
    "enable",
    "disable",
    "toggle",
    "next",
    "previous",
    "zoom_in",
    "zoom_out",
    "zoom_reset"
  ]);
  const ACTION_SET = new Set(ACTIONS);
  const POLL_INTERVAL_MS = 1500;
  const MIN_ZOOM = 1;
  const MAX_ZOOM = 4;
  const FOCAL_ACTIONS = new Set(["zoom_in", "zoom_out"]);

  function normalizedFocusPoint(value) {
    if (!value || typeof value !== "object") return null;
    const x = Number(value.x);
    const y = Number(value.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    return {
      x: Math.max(0, Math.min(1, x)),
      y: Math.max(0, Math.min(1, y))
    };
  }

  function presentationActionPayload(action, focusPoint = null) {
    const normalized = String(action || "").trim().toLowerCase();
    if (!ACTION_SET.has(normalized)) {
      throw new Error("Unsupported presentation action");
    }
    const payload = {action: normalized};
    const focus = normalizedFocusPoint(focusPoint);
    if (focus && FOCAL_ACTIONS.has(normalized)) {
      payload.x = focus.x;
      payload.y = focus.y;
    }
    return payload;
  }

  function normalizePresentationState(value) {
    const source = value && typeof value === "object" ? value : {};
    const parsedZoom = Number(source.zoom);
    const boundedZoom = Number.isFinite(parsedZoom)
      ? Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, parsedZoom))
      : MIN_ZOOM;
    const parsedRevision = Number(source.revision);
    return {
      enabled: source.enabled === true,
      zoom: Math.round(boundedZoom * 4) / 4,
      revision: Number.isFinite(parsedRevision)
        ? Math.max(0, Math.trunc(parsedRevision))
        : 0
    };
  }

  function shouldApplyPresentationState(current, candidate) {
    return !current || candidate.revision >= current.revision;
  }

  function create(options) {
    const {
      request,
      rootElement,
      modeControl,
      toggle,
      controls,
      modeText,
      zoomText,
      previousButton,
      nextButton,
      zoomOutButton,
      zoomResetButton,
      zoomInButton,
      getFocusPoint = () => null,
      resetPhoneZoom = () => {}
    } = options;
    const actionButtons = [
      previousButton,
      nextButton,
      zoomOutButton,
      zoomResetButton,
      zoomInButton
    ];
    let state = null;
    let stopped = true;
    let pollTimer = null;
    let feedbackTimer = null;
    let pending = 0;
    let terminal = false;

    function setClass(element, name, active) {
      if (element && element.classList) {
        element.classList.toggle(name, active);
      }
    }

    function showControls(visible) {
      controls.hidden = !visible;
      controls.setAttribute("aria-hidden", String(!visible));
      setClass(rootElement, "presentation-active", visible);
    }

    function renderBusy() {
      const busy = pending > 0;
      const enabled = Boolean(state && state.enabled);
      const zoom = state ? state.zoom : MIN_ZOOM;
      toggle.disabled = terminal || busy;
      actionButtons.forEach(button => {
        button.disabled = terminal || busy || !enabled;
      });
      zoomOutButton.disabled = terminal || busy || !enabled || zoom <= MIN_ZOOM;
      zoomResetButton.disabled = terminal || busy || !enabled || zoom <= MIN_ZOOM;
      zoomInButton.disabled = terminal || busy || !enabled || zoom >= MAX_ZOOM;
      setClass(controls, "is-busy", busy);
    }

    function clearFeedback() {
      if (feedbackTimer) clearTimeout(feedbackTimer);
      feedbackTimer = null;
      setClass(modeControl, "has-error", false);
    }

    function render(nextState) {
      const candidate = normalizePresentationState(nextState);
      if (!shouldApplyPresentationState(state, candidate)) return state;
      state = candidate;
      clearFeedback();
      toggle.checked = state.enabled;
      showControls(state.enabled);
      modeText.textContent = state.enabled ? "PPT On" : "PPT Present";
      const zoomSteps = Math.round((state.zoom - MIN_ZOOM) * 4);
      const zoomSummary = zoomSteps ? `Laptop zoom +${zoomSteps}` : "Laptop zoom ready";
      zoomText.textContent = zoomSummary;
      zoomResetButton.textContent = zoomSteps ? `Reset ${zoomSteps}` : "Reset";
      zoomResetButton.setAttribute(
        "aria-label",
        zoomSteps
          ? `Reset ${zoomSteps} laptop magnifier steps`
          : "Laptop magnifier is at its starting level"
      );
      renderBusy();
      return state;
    }

    function showError(error) {
      toggle.checked = Boolean(state && state.enabled);
      showControls(Boolean(state && state.enabled));
      const status = Number(error && error.status);
      modeText.textContent = status === 404
        ? "Restart laptop app"
        : status === 401
          ? "Reconnect screen"
          : "PPT reconnecting";
      setClass(modeControl, "has-error", true);
      if (feedbackTimer) clearTimeout(feedbackTimer);
      if (status === 404 || status === 401) {
        feedbackTimer = null;
        return;
      }
      feedbackTimer = setTimeout(() => {
        feedbackTimer = null;
        setClass(modeControl, "has-error", false);
        modeText.textContent = state && state.enabled ? "PPT On" : "PPT Present";
      }, 2200);
    }

    async function readResponse(response) {
      if (!response || !response.ok) {
        const status = response && response.status ? ` ${response.status}` : "";
        const error = new Error(`Presentation request failed${status}`);
        error.status = response && response.status ? response.status : 0;
        throw error;
      }
      return normalizePresentationState(await response.json());
    }

    function endSession() {
      terminal = true;
      const revision = state ? state.revision + 1 : 0;
      render({enabled: false, zoom: MIN_ZOOM, revision});
      modeText.textContent = "PPT unavailable";
      stop();
      renderBusy();
    }

    async function sync(quiet = false) {
      try {
        const response = await request("/v1/screen/presentation");
        if (response && response.status === 403) {
          endSession();
          return state;
        }
        const nextState = await readResponse(response);
        // An older poll must not undo the optimistic checkbox while a user
        // action is in flight. The action response (or next poll) owns render.
        if (pending > 0) return state;
        return render(nextState);
      } catch (error) {
        if (!quiet) showError(error);
        return state;
      }
    }

    async function action(name) {
      const payload = presentationActionPayload(name, getFocusPoint());
      const optimisticEnabled = payload.action === "enable"
        ? true
        : payload.action === "disable"
          ? false
          : null;
      if (optimisticEnabled !== null) {
        toggle.checked = optimisticEnabled;
        showControls(optimisticEnabled);
        modeText.textContent = optimisticEnabled ? "Starting PPT…" : "Closing PPT…";
      }
      pending += 1;
      renderBusy();
      try {
        const response = await request("/v1/screen/presentation/actions", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        if (response && response.status === 403) {
          endSession();
          return state;
        }
        const rendered = render(await readResponse(response));
        if (FOCAL_ACTIONS.has(payload.action) || payload.action === "zoom_reset") {
          resetPhoneZoom();
        }
        return rendered;
      } catch (error) {
        showError(error);
        return state;
      } finally {
        pending = Math.max(0, pending - 1);
        renderBusy();
      }
    }

    function schedulePoll() {
      if (stopped) return;
      pollTimer = setTimeout(async () => {
        await sync(true);
        schedulePoll();
      }, POLL_INTERVAL_MS);
    }

    async function start() {
      if (!stopped) return state;
      terminal = false;
      stopped = false;
      await sync(false);
      schedulePoll();
      return state;
    }

    function stop() {
      stopped = true;
      if (pollTimer) clearTimeout(pollTimer);
      if (feedbackTimer) clearTimeout(feedbackTimer);
      pollTimer = null;
      feedbackTimer = null;
    }

    toggle.addEventListener("change", () => {
      action(toggle.checked ? "enable" : "disable");
    });
    previousButton.addEventListener("click", () => action("previous"));
    nextButton.addEventListener("click", () => action("next"));
    zoomOutButton.addEventListener("click", () => action("zoom_out"));
    zoomResetButton.addEventListener("click", () => action("zoom_reset"));
    zoomInButton.addEventListener("click", () => action("zoom_in"));
    ["pointerdown", "pointermove", "pointerup", "pointercancel"].forEach(type => {
      [modeControl, controls].forEach(element => {
        element.addEventListener(type, event => event.stopPropagation());
      });
    });
    showControls(false);
    renderBusy();

    return Object.freeze({
      action,
      isEnabled() {
        return Boolean(state && state.enabled);
      },
      start,
      stop,
      sync
    });
  }

  root.AkshPresentation = Object.freeze({
    ACTIONS,
    POLL_INTERVAL_MS,
    create,
    normalizePresentationState,
    normalizedFocusPoint,
    presentationActionPayload,
    shouldApplyPresentationState
  });
})(typeof window !== "undefined" ? window : globalThis);
