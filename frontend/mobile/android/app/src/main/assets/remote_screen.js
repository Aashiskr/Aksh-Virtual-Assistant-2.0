(() => {
  "use strict";
  const config = JSON.parse(AkshBridge.configuration());
  const screenArea = document.getElementById("screenArea");
  const video = document.getElementById("remoteVideo");
  const frame = document.getElementById("fallbackFrame");
  const loading = document.getElementById("loading");
  const status = document.getElementById("status");
  const textInput = document.getElementById("textInput");
  const focusIndicator = document.getElementById("presentationFocusIndicator");
  const zoom = AkshZoom.create({
    screenArea,
    video,
    frame,
    controls: document.getElementById("zoomControls"),
    outButton: document.getElementById("zoomOutButton"),
    valueButton: document.getElementById("zoomValueButton"),
    inButton: document.getElementById("zoomInButton")
  });
  function setStatus(text, failed = false) {
    status.textContent = text;
    status.style.color = failed ? "var(--error)" : "var(--accent)";
  }

  const transport = AkshRemoteTransport.create({
    config,
    video,
    frame,
    loading,
    setStatus
  });
  const sendInput = payload => transport.sendInput(payload);
  let presentation = null;
  const gestures = AkshGestures.create({
    screenArea,
    video,
    frame,
    zoom,
    sendInput,
    isPresentationActive: () => Boolean(presentation && presentation.isEnabled()),
    focusIndicator
  });
  presentation = AkshPresentation.create({
    request: transport.request,
    rootElement: document.body,
    modeControl: document.getElementById("pptModeControl"),
    toggle: document.getElementById("pptPresentToggle"),
    controls: document.getElementById("presentationControls"),
    modeText: document.getElementById("presentationModeText"),
    zoomText: document.getElementById("presentationZoomText"),
    previousButton: document.getElementById("presentationPreviousButton"),
    nextButton: document.getElementById("presentationNextButton"),
    zoomOutButton: document.getElementById("presentationZoomOutButton"),
    zoomResetButton: document.getElementById("presentationZoomResetButton"),
    zoomInButton: document.getElementById("presentationZoomInButton"),
    getFocusPoint: gestures.getFocusPoint,
    resetPhoneZoom: () => {
      zoom.reset();
      focusIndicator.hidden = true;
    }
  });

  document.querySelectorAll("[data-key]").forEach(button => {
    button.addEventListener("click", () => {
      sendInput({action: "key", key: button.dataset.key});
    });
  });
  AkshRemoteControls.bind(document, sendInput);
  document.getElementById("rightClickButton").addEventListener(
    "click", gestures.rightClick
  );
  document.getElementById("sendTextButton").addEventListener("click", () => {
    const text = textInput.value;
    if (!text) return;
    sendInput({action: "text", text});
    textInput.value = "";
  });
  textInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("sendTextButton").click();
    }
  });
  document.getElementById("closeButton").addEventListener(
    "click", () => AkshBridge.closeScreen()
  );
  document.getElementById("refreshButton").addEventListener(
    "click", transport.start
  );
  window.addEventListener("beforeunload", () => {
    presentation.stop();
    transport.stop();
  });
  window.addEventListener("resize", () => {
    focusIndicator.hidden = true;
  });
  transport.start();
  presentation.start();
})();
