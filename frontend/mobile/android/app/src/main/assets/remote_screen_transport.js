(() => {
  "use strict";

  const FRAME_INTERVAL_MS = 650;
  const HEARTBEAT_INTERVAL_MS = 20000;

  function retryDelay(failureCount) {
    const exponent = Math.min(3, Math.max(0, Number(failureCount) - 1));
    return Math.min(6000, 800 * (2 ** exponent));
  }

  function isWebRtcLive(connectionState, receivedTrack) {
    return connectionState === "connected" && Boolean(receivedTrack);
  }

  function shouldRefreshEndpoint(failureCount) {
    return failureCount >= 3 && (failureCount - 3) % 5 === 0;
  }

  function isTerminalSessionStatus(status) {
    return Number(status) === 403;
  }

  function create({config, video, frame, loading, setStatus}) {
    let peer = null;
    let inputChannel = null;
    let fallbackActive = false;
    let fallbackTimer = null;
    let connectionTimer = null;
    let heartbeatTimer = null;
    let disconnectedTimer = null;
    let lastFrameUrl = "";
    let stopped = true;
    let generation = 0;
    let failureCount = 0;
    let webRtcLive = false;
    const session = AkshRemoteSession.create({config, setStatus});

    function clearTimer(timer) {
      if (timer) clearTimeout(timer);
      return null;
    }

    function closePeer() {
      inputChannel = null;
      if (!peer) return;
      peer.onconnectionstatechange = null;
      peer.ontrack = null;
      peer.close();
      peer = null;
    }

    function releaseDisplayedMedia() {
      video.srcObject = null;
      video.style.display = "none";
      frame.style.display = "none";
      frame.removeAttribute("src");
      if (lastFrameUrl) URL.revokeObjectURL(lastFrameUrl);
      lastFrameUrl = "";
    }

    function stop() {
      stopped = true;
      generation += 1;
      fallbackActive = false;
      connectionTimer = clearTimer(connectionTimer);
      fallbackTimer = clearTimer(fallbackTimer);
      heartbeatTimer = clearTimer(heartbeatTimer);
      disconnectedTimer = clearTimer(disconnectedTimer);
      closePeer();
      releaseDisplayedMedia();
    }

    function scheduleHeartbeat(run) {
      heartbeatTimer = clearTimer(heartbeatTimer);
      heartbeatTimer = setTimeout(async () => {
        if (stopped || run !== generation || fallbackActive) return;
        try {
          const response = await session.request(
            "/v1/screen/sessions/current/heartbeat",
            {method: "POST", body: "{}"}
          );
          if (!response.ok) throw new Error(`Heartbeat HTTP ${response.status}`);
        } catch (_) {
          // The WebRTC stream may still be healthy during a brief tunnel outage.
        } finally {
          if (!stopped && run === generation && !fallbackActive) {
            scheduleHeartbeat(run);
          }
        }
      }, HEARTBEAT_INTERVAL_MS);
    }

    function activateFallback(run) {
      if (stopped || run !== generation || fallbackActive) return;
      fallbackActive = true;
      connectionTimer = clearTimer(connectionTimer);
      disconnectedTimer = clearTimer(disconnectedTimer);
      heartbeatTimer = clearTimer(heartbeatTimer);
      closePeer();
      webRtcLive = false;
      video.style.display = "none";
      if (frame.style.display !== "block") loading.style.display = "flex";
      setStatus("SECURE INTERNET MODE");
      pollFrame(run);
    }

    async function pollFrame(run) {
      if (stopped || run !== generation || !fallbackActive) return;
      let delay = FRAME_INTERVAL_MS;
      try {
        const response = await session.request(
          `/v1/screen/frame?t=${Date.now()}`
        );
        if (isTerminalSessionStatus(response.status)) {
          fallbackActive = false;
          loading.style.display = "flex";
          setStatus("SCREEN ACCESS ENDED", true);
          return;
        }
        if (!response.ok) throw new Error(`Frame HTTP ${response.status}`);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        if (stopped || run !== generation || !fallbackActive) {
          URL.revokeObjectURL(url);
          return;
        }
        frame.onload = () => {
          if (lastFrameUrl) URL.revokeObjectURL(lastFrameUrl);
          lastFrameUrl = url;
        };
        frame.src = url;
        frame.style.display = "block";
        loading.style.display = "none";
        failureCount = 0;
        setStatus("LIVE - SECURE INTERNET");
      } catch (_) {
        failureCount += 1;
        delay = retryDelay(failureCount);
        setStatus("RECONNECTING AUTOMATICALLY", true);
        if (shouldRefreshEndpoint(failureCount)) {
          AkshBridge.refreshConnection();
        }
      } finally {
        if (!stopped && run === generation && fallbackActive) {
          fallbackTimer = setTimeout(() => pollFrame(run), delay);
        }
      }
    }

    function waitForIce(connection, timeout) {
      if (connection.iceGatheringState === "complete") {
        return Promise.resolve();
      }
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

    async function startWebRtc(run) {
      try {
        peer = new RTCPeerConnection({
          iceServers: [{urls: "stun:stun.cloudflare.com:3478"}]
        });
        const currentPeer = peer;
        let receivedTrack = false;
        const showWebRtcWhenReady = () => {
          if (
            stopped
            || run !== generation
            || currentPeer !== peer
            || !isWebRtcLive(currentPeer.connectionState, receivedTrack)
          ) {
            return;
          }
          webRtcLive = true;
          video.style.display = "block";
          frame.style.display = "none";
          loading.style.display = "none";
          connectionTimer = clearTimer(connectionTimer);
          setStatus("LIVE - WEBRTC");
          scheduleHeartbeat(run);
        };
        currentPeer.addTransceiver("video", {direction: "recvonly"});
        inputChannel = currentPeer.createDataChannel("input", {ordered: true});
        currentPeer.ontrack = event => {
          if (stopped || run !== generation || currentPeer !== peer) return;
          receivedTrack = true;
          video.srcObject = event.streams[0] || new MediaStream([event.track]);
          showWebRtcWhenReady();
        };
        currentPeer.onconnectionstatechange = () => {
          if (stopped || run !== generation || currentPeer !== peer) return;
          const state = currentPeer.connectionState;
          if (state === "failed" || state === "closed") {
            activateFallback(run);
          } else if (state === "disconnected") {
            disconnectedTimer = clearTimer(disconnectedTimer);
            disconnectedTimer = setTimeout(() => {
              if (currentPeer.connectionState === "disconnected") {
                activateFallback(run);
              }
            }, 2500);
          } else if (state === "connected") {
            disconnectedTimer = clearTimer(disconnectedTimer);
            showWebRtcWhenReady();
          }
        };
        const offer = await currentPeer.createOffer();
        await currentPeer.setLocalDescription(offer);
        await waitForIce(currentPeer, 5000);
        if (stopped || run !== generation || currentPeer !== peer) return;
        const response = await session.request("/v1/screen/webrtc/offer", {
          method: "POST",
          body: JSON.stringify(currentPeer.localDescription)
        });
        if (!response.ok) throw new Error(`WebRTC HTTP ${response.status}`);
        await currentPeer.setRemoteDescription(await response.json());
        if (!webRtcLive) {
          connectionTimer = setTimeout(() => {
            if (!webRtcLive) activateFallback(run);
          }, 7000);
        }
      } catch (_) {
        activateFallback(run);
      }
    }

    function start() {
      stop();
      stopped = false;
      const run = generation;
      fallbackActive = false;
      failureCount = 0;
      webRtcLive = false;
      loading.style.display = "flex";
      setStatus("CONNECTING");
      startWebRtc(run);
    }

    function sendInput(payload) {
      if (inputChannel && inputChannel.readyState === "open") {
        inputChannel.send(JSON.stringify(payload));
        return;
      }
      session.request("/v1/screen/input", {
        method: "POST",
        body: JSON.stringify(payload)
      }).then(response => {
        if (!response.ok) throw new Error(`Input HTTP ${response.status}`);
      }).catch(() => setStatus("INPUT NOT SENT - RECONNECTING", true));
    }

    // Reuse this authenticated session for companion screen features. Creating
    // another session helper could independently renew and invalidate WebRTC.
    return {start, stop, sendInput, request: session.request};
  }

  window.AkshRemoteTransport = {
    create,
    isWebRtcLive,
    isTerminalSessionStatus,
    retryDelay,
    shouldRefreshEndpoint
  };
})();
