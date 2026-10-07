import assert from "node:assert/strict";
import test from "node:test";

globalThis.window = {};
await import("./app/src/main/assets/remote_screen_zoom.js");
await import("./app/src/main/assets/remote_screen_gestures.js");
await import("./app/src/main/assets/remote_screen_controls.js");
await import("./app/src/main/assets/remote_screen_presentation.js");
await import("./app/src/main/assets/remote_screen_session.js");
await import("./app/src/main/assets/remote_screen_transport.js");

const {anchoredPan} = window.AkshZoom;
const {classifyOneFinger, create: createGestures} = window.AkshGestures;
const {SCROLL_STEP, scrollPayload} = window.AkshRemoteControls;
const {
  create: createPresentation,
  normalizePresentationState,
  normalizedFocusPoint,
  presentationActionPayload,
  shouldApplyPresentationState,
} = window.AkshPresentation;
const {create: createSession, notifySessionChanged} = window.AkshRemoteSession;
const {
  isWebRtcLive,
  isTerminalSessionStatus,
  retryDelay,
  shouldRefreshEndpoint,
} = window.AkshRemoteTransport;

function fakeElement() {
  const attributes = new Map();
  const classes = new Set();
  const listeners = new Map();
  return {
    checked: false,
    disabled: false,
    hidden: false,
    style: {},
    textContent: "",
    classList: {
      contains: name => classes.has(name),
      toggle(name, active) {
        if (active) classes.add(name);
        else classes.delete(name);
      },
    },
    addEventListener(name, listener) {
      listeners.set(name, listener);
    },
    dispatch(name, event = {}) {
      const listener = listeners.get(name);
      if (listener) listener(event);
    },
    getAttribute(name) {
      return attributes.get(name);
    },
    setAttribute(name, value) {
      attributes.set(name, String(value));
    },
  };
}

test("small one-finger movement stays a tap", () => {
  assert.equal(classifyOneFinger(3, 4), "pending");
});

test("deliberate vertical one-finger swipe scrolls", () => {
  assert.equal(classifyOneFinger(3, -24), "scroll");
  assert.equal(classifyOneFinger(-2, 24), "scroll");
});

test("horizontal or diagonal one-finger motion remains pointer drag", () => {
  assert.equal(classifyOneFinger(24, 3), "drag");
  assert.equal(classifyOneFinger(18, 16), "drag");
});

test("phone preview zoom preserves an off-centre touch anchor", () => {
  const next = anchoredPan({
    panX: 0,
    panY: 0,
    oldLevel: 1,
    newLevel: 2,
    focusX: 150,
    focusY: 25,
    centerX: 100,
    centerY: 50,
  });
  assert.deepEqual(next, {x: -50, y: 25});
  assert.equal(100 + (150 - 100) * 2 + next.x, 150);
  assert.equal(50 + (25 - 50) * 2 + next.y, 25);
});

test("PPT tap selects zoom focus without clicking the laptop", () => {
  const screenArea = fakeElement();
  screenArea.getBoundingClientRect = () => ({
    left: 0,
    top: 0,
    width: 200,
    height: 100,
  });
  screenArea.setPointerCapture = () => {};
  const video = {style: {display: "block"}, videoWidth: 200, videoHeight: 100};
  const frame = {naturalWidth: 0, naturalHeight: 0};
  const focusIndicator = fakeElement();
  const inputs = [];
  const selected = [];
  const gestures = createGestures({
    screenArea,
    video,
    frame,
    zoom: {
      adjustContentBox: box => box,
      beginTwoFinger() {},
      endTwoFinger() {},
      moveTwoFinger: () => ({type: "pending"}),
      rememberFocus() {},
    },
    sendInput: payload => inputs.push(payload),
    isPresentationActive: () => true,
    focusIndicator,
    onFocusPoint: point => selected.push(point),
  });
  const event = {
    pointerId: 1,
    clientX: 150,
    clientY: 25,
    preventDefault() {},
  };
  screenArea.dispatch("pointerdown", event);
  screenArea.dispatch("pointerup", event);

  assert.deepEqual(inputs, []);
  assert.deepEqual(selected, [{x: .75, y: .25, source: "tap"}]);
  assert.deepEqual(gestures.getFocusPoint(), {x: .75, y: .25});
  assert.equal(focusIndicator.hidden, false);
  assert.equal(focusIndicator.style.left, "150px");
  assert.equal(focusIndicator.style.top, "25px");
});

test("scroll buttons target the current laptop page in both directions", () => {
  assert.deepEqual(scrollPayload("up"), {
    action: "scroll",
    delta: SCROLL_STEP,
  });
  assert.deepEqual(scrollPayload("down"), {
    action: "scroll",
    delta: -SCROLL_STEP,
  });
});

test("scroll buttons reject unknown directions", () => {
  assert.throws(() => scrollPayload("sideways"));
});

test("presentation actions use the dedicated allow-listed API payload", () => {
  assert.deepEqual(presentationActionPayload(" next "), {action: "next"});
  assert.deepEqual(presentationActionPayload("PREVIOUS"), {action: "previous"});
  assert.deepEqual(presentationActionPayload("zoom_in"), {action: "zoom_in"});
  assert.deepEqual(presentationActionPayload("zoom_out"), {action: "zoom_out"});
  assert.deepEqual(presentationActionPayload("zoom_reset"), {action: "zoom_reset"});
  assert.deepEqual(presentationActionPayload("enable"), {action: "enable"});
  assert.deepEqual(presentationActionPayload("disable"), {action: "disable"});
  assert.deepEqual(
    presentationActionPayload("zoom_in", {x: .82, y: .17}),
    {action: "zoom_in", x: .82, y: .17},
  );
  assert.deepEqual(
    presentationActionPayload("zoom_out", {x: 4, y: -2}),
    {action: "zoom_out", x: 1, y: 0},
  );
  assert.deepEqual(
    presentationActionPayload("next", {x: .82, y: .17}),
    {action: "next"},
  );
  assert.deepEqual(normalizedFocusPoint({x: "bad", y: .5}), null);
  assert.throws(() => presentationActionPayload("page_down"));
});

test("presentation state is bounded and safe to render", () => {
  assert.deepEqual(
    normalizePresentationState({enabled: true, zoom: 1.26, revision: 7.9}),
    {enabled: true, zoom: 1.25, revision: 7},
  );
  assert.deepEqual(
    normalizePresentationState({enabled: false, zoom: 99, revision: -2}),
    {enabled: false, zoom: 4, revision: 0},
  );
  assert.deepEqual(
    normalizePresentationState({enabled: "true", zoom: "bad"}),
    {enabled: false, zoom: 1, revision: 0},
  );
});

test("older presentation polls cannot overwrite a newer action response", () => {
  assert.equal(
    shouldApplyPresentationState({revision: 9}, {revision: 8}),
    false,
  );
  assert.equal(
    shouldApplyPresentationState({revision: 9}, {revision: 9}),
    true,
  );
  assert.equal(shouldApplyPresentationState(null, {revision: 0}), true);
});

test("presentation controller uses one authenticated request function and renders state", async () => {
  let serverState = {enabled: false, zoom: 1, revision: 0};
  const calls = [];
  const request = async (path, options = {}) => {
    calls.push({path, options});
    const payload = options.body ? JSON.parse(options.body) : null;
    if (payload?.action === "enable") {
      serverState = {enabled: true, zoom: 1, revision: 1};
    } else if (payload?.action === "zoom_in") {
      serverState = {enabled: true, zoom: 1.25, revision: 2};
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({...serverState}),
    };
  };
  const rootElement = fakeElement();
  const modeControl = fakeElement();
  const toggle = fakeElement();
  const controls = fakeElement();
  const modeText = fakeElement();
  const zoomText = fakeElement();
  const previousButton = fakeElement();
  const nextButton = fakeElement();
  const zoomOutButton = fakeElement();
  const zoomResetButton = fakeElement();
  const zoomInButton = fakeElement();
  let phoneZoomResets = 0;
  const controller = createPresentation({
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
    getFocusPoint: () => ({x: .8, y: .2}),
    resetPhoneZoom: () => { phoneZoomResets += 1; },
  });

  await controller.sync();
  assert.equal(calls[0].path, "/v1/screen/presentation");
  assert.equal(controls.hidden, true);
  await controller.action("enable");
  assert.equal(calls[1].path, "/v1/screen/presentation/actions");
  assert.equal(calls[1].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[1].options.body), {action: "enable"});
  assert.equal(toggle.checked, true);
  assert.equal(controls.hidden, false);
  assert.equal(rootElement.classList.contains("presentation-active"), true);
  assert.equal(nextButton.disabled, false);
  let pointerStopped = false;
  controls.dispatch("pointerdown", {
    stopPropagation() {
      pointerStopped = true;
    },
  });
  assert.equal(pointerStopped, true);
  let togglePointerStopped = false;
  modeControl.dispatch("pointerdown", {
    stopPropagation() {
      togglePointerStopped = true;
    },
  });
  assert.equal(togglePointerStopped, true);

  await controller.action("zoom_in");
  assert.deepEqual(JSON.parse(calls[2].options.body), {
    action: "zoom_in",
    x: .8,
    y: .2,
  });
  assert.equal(phoneZoomResets, 1);
  assert.equal(zoomText.textContent, "Laptop zoom +1");
  assert.equal(zoomResetButton.textContent, "Reset 1");
  assert.equal(
    zoomResetButton.getAttribute("aria-label"),
    "Reset 1 laptop magnifier steps"
  );
  controller.stop();
});

test("presentation controller asks for a laptop restart when the live API is old", async () => {
  const elements = Array.from({length: 10}, () => fakeElement());
  const [
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
  ] = elements;
  const zoomInButton = fakeElement();
  const controller = createPresentation({
    request: async () => ({ok: false, status: 404}),
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
  });

  await controller.action("enable");
  assert.equal(toggle.checked, false);
  assert.equal(modeText.textContent, "Restart laptop app");
  assert.equal(modeControl.classList.contains("has-error"), true);
  await new Promise(resolve => setTimeout(resolve, 2250));
  assert.equal(modeText.textContent, "Restart laptop app");
  assert.equal(modeControl.classList.contains("has-error"), true);
  controller.stop();
});

test("renewed screen session is reported to the Android lifecycle bridge", () => {
  const reported = [];
  const bridge = {
    updateScreenSession(sessionId) {
      reported.push(sessionId);
    },
  };
  assert.equal(notifySessionChanged(bridge, "session-new"), true);
  assert.deepEqual(reported, ["session-new"]);
  assert.equal(notifySessionChanged(bridge, "  "), false);
  assert.equal(notifySessionChanged(null, "session-newer"), false);
});

test("only an expired session renews; a replaced session stays terminal", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async url => {
      calls.push(String(url));
      return {ok: false, status: 403};
    };
    const replaced = createSession({
      config: {baseUrl: "https://laptop.test", token: "t", sessionId: "old"},
      setStatus() {},
    });
    const forbidden = await replaced.request("/protected");
    assert.equal(forbidden.status, 403);
    assert.equal(calls.length, 1);

    calls.length = 0;
    let protectedAttempts = 0;
    globalThis.fetch = async url => {
      calls.push(String(url));
      if (String(url).endsWith("/v1/screen/sessions")) {
        return {
          ok: true,
          status: 201,
          json: async () => ({session_id: "renewed"}),
        };
      }
      protectedAttempts += 1;
      return {
        ok: protectedAttempts > 1,
        status: protectedAttempts > 1 ? 200 : 401,
      };
    };
    const expired = createSession({
      config: {baseUrl: "https://laptop.test", token: "t", sessionId: "old"},
      setStatus() {},
    });
    const renewed = await expired.request("/protected");
    assert.equal(renewed.status, 200);
    assert.equal(calls.length, 3);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("remote-screen reconnect uses bounded exponential backoff", () => {
  assert.equal(retryDelay(1), 800);
  assert.equal(retryDelay(2), 1600);
  assert.equal(retryDelay(3), 3200);
  assert.equal(retryDelay(50), 6000);
});

test("a replaced or disabled session is terminal for automatic recovery", () => {
  assert.equal(isTerminalSessionStatus(403), true);
  assert.equal(isTerminalSessionStatus(401), false);
  assert.equal(isTerminalSessionStatus(503), false);
});

test("a signaled track is not live until WebRTC actually connects", () => {
  assert.equal(isWebRtcLive("connecting", true), false);
  assert.equal(isWebRtcLive("connected", false), false);
  assert.equal(isWebRtcLive("connected", true), true);
});

test("repeated frame failures periodically request a fresh tunnel URL", () => {
  assert.equal(shouldRefreshEndpoint(2), false);
  assert.equal(shouldRefreshEndpoint(3), true);
  assert.equal(shouldRefreshEndpoint(4), false);
  assert.equal(shouldRefreshEndpoint(8), true);
});
