(() => {
  "use strict";
  const config = JSON.parse(AkshBridge.configuration());
  const screenArea = document.getElementById("screenArea");
  const video = document.getElementById("remoteVideo");
  const frame = document.getElementById("fallbackFrame");
  const loading = document.getElementById("loading");
  const status = document.getElementById("status");
  const textInput = document.getElementById("textInput");
  const zoom = AkshZoom.create({
    video,
    frame,
    controls: document.getElementById("zoomControls"),
    outButton: document.getElementById("zoomOutButton"),
    valueButton: document.getElementById("zoomValueButton"),
    inButton: document.getElementById("zoomInButton")
  });
  let peer = null;
  let inputChannel = null;
  let fallbackActive = false;
  let fallbackTimer = null;
  let connectionTimer = null;
  let lastFrameUrl = "";

  const headers = (json = false) => ({
    "Authorization": `Bearer ${config.token}`,
    "X-Aksh-Screen-Session": config.sessionId,
    ...(json ? {"Content-Type": "application/json"} : {})
  });

  function setStatus(text, failed = false) {
    status.textContent = text;
    status.style.color = failed ? "var(--error)" : "var(--accent)";
  }

  async function startWebRtc() {
    stopConnections();
    fallbackActive = false;
    loading.style.display = "flex";
    setStatus("CONNECTING");
    try {
      peer = new RTCPeerConnection({
        iceServers: [{urls: "stun:stun.cloudflare.com:3478"}]
      });
      peer.addTransceiver("video", {direction: "recvonly"});
      inputChannel = peer.createDataChannel("input", {ordered: true});
      peer.ontrack = event => {
        video.srcObject = event.streams[0] || new MediaStream([event.track]);
        video.style.display = "block";
        frame.style.display = "none";
        loading.style.display = "none";
        setStatus("LIVE - WEBRTC");
      };
      peer.onconnectionstatechange = () => {
        const current = peer;
        if (current && ["failed", "closed"].includes(current.connectionState)) {
          startFallback();
        }
      };
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      await waitForIce(peer, 6500);
      const response = await fetch(`${config.baseUrl}/v1/screen/webrtc/offer`, {
        method: "POST",
        headers: headers(true),
        body: JSON.stringify(peer.localDescription)
      });
      if (!response.ok) throw new Error(await response.text());
      await peer.setRemoteDescription(await response.json());
      connectionTimer = setTimeout(() => {
        if (video.style.display !== "block") startFallback();
      }, 9000);
    } catch (error) {
      startFallback();
    }
  }

  function waitForIce(connection, timeout) {
    if (connection.iceGatheringState === "complete") return Promise.resolve();
    return new Promise(resolve => {
      const done = () => {
        connection.removeEventListener("icegatheringstatechange", changed);
        clearTimeout(timer);
        resolve();
      };
      const changed = () => {
        if (connection.iceGatheringState === "complete") done();
      };
      const timer = setTimeout(done, timeout);
      connection.addEventListener("icegatheringstatechange", changed);
    });
  }

  function startFallback() {
    if (fallbackActive) return;
    fallbackActive = true;
    if (connectionTimer) clearTimeout(connectionTimer);
    if (peer) peer.close();
    peer = null;
    inputChannel = null;
    video.style.display = "none";
    loading.style.display = "flex";
    setStatus("SECURE FALLBACK");
    pollFrame();
  }

  async function pollFrame() {
    if (!fallbackActive) return;
    try {
      const response = await fetch(
        `${config.baseUrl}/v1/screen/frame?t=${Date.now()}`,
        {headers: headers()}
      );
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      frame.onload = () => {
        if (lastFrameUrl) URL.revokeObjectURL(lastFrameUrl);
        lastFrameUrl = url;
      };
      frame.src = url;
      frame.style.display = "block";
      loading.style.display = "none";
      setStatus("LIVE - HTTPS FALLBACK");
    } catch (error) {
      setStatus("RECONNECTING", true);
    } finally {
      fallbackTimer = setTimeout(pollFrame, 650);
    }
  }

  function stopConnections() {
    if (connectionTimer) clearTimeout(connectionTimer);
    if (fallbackTimer) clearTimeout(fallbackTimer);
    if (peer) peer.close();
    connectionTimer = null;
    fallbackTimer = null;
    peer = null;
    inputChannel = null;
  }

  function sendInput(payload) {
    if (inputChannel && inputChannel.readyState === "open") {
      inputChannel.send(JSON.stringify(payload));
      return;
    }
    fetch(`${config.baseUrl}/v1/screen/input`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(payload)
    }).catch(() => setStatus("INPUT RETRY", true));
  }

  const gestures = AkshGestures.create({screenArea, video, frame, zoom, sendInput});
  document.querySelectorAll("[data-key]").forEach(button => {
    button.addEventListener("click", () => {
      sendInput({action: "key", key: button.dataset.key});
    });
  });
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
    "click", startWebRtc
  );
  window.addEventListener("beforeunload", stopConnections);
  startWebRtc();
})();
