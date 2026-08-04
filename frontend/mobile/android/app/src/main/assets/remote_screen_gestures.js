(() => {
  "use strict";

  function classifyOneFinger(deltaX, deltaY) {
    if (Math.hypot(deltaX, deltaY) < 10) return "pending";
    return Math.abs(deltaY) > Math.abs(deltaX) * 1.2 ? "scroll" : "drag";
  }

  function create({screenArea, video, frame, zoom, sendInput}) {
    let lastTapAt = 0;
    let lastTapPosition = null;
    let lastPointerPosition = {x: .5, y: .5};
    let longPressTimer = null;
    let dragStarted = false;
    let longPressTriggered = false;
    let multiTouchGesture = false;
    let lastMoveAt = 0;
    let oneFingerMode = "pending";
    let primaryStart = null;
    const pointers = new Map();

    function contentPoint(clientX, clientY) {
      const rect = screenArea.getBoundingClientRect();
      const source = video.style.display === "block" ? video : frame;
      const naturalWidth = source === video ? video.videoWidth : frame.naturalWidth;
      const naturalHeight = source === video ? video.videoHeight : frame.naturalHeight;
      if (!naturalWidth || !naturalHeight) return null;
      const sourceRatio = naturalWidth / naturalHeight;
      const areaRatio = rect.width / rect.height;
      let width = rect.width;
      let height = rect.height;
      let offsetX = 0;
      let offsetY = 0;
      if (sourceRatio > areaRatio) {
        height = width / sourceRatio;
        offsetY = (rect.height - height) / 2;
      } else {
        width = height * sourceRatio;
        offsetX = (rect.width - width) / 2;
      }
      const content = zoom.adjustContentBox({width, height, offsetX, offsetY});
      const point = {
        x: Math.max(0, Math.min(1, (clientX - rect.left - content.offsetX) / content.width)),
        y: Math.max(0, Math.min(1, (clientY - rect.top - content.offsetY) / content.height))
      };
      lastPointerPosition = point;
      return point;
    }

    screenArea.addEventListener("pointerdown", event => {
      event.preventDefault();
      screenArea.setPointerCapture(event.pointerId);
      pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
      if (pointers.size === 1) {
        multiTouchGesture = false;
        dragStarted = false;
        longPressTriggered = false;
        oneFingerMode = "pending";
        primaryStart = {x: event.clientX, y: event.clientY};
        longPressTimer = setTimeout(() => {
          const point = contentPoint(event.clientX, event.clientY);
          if (point && !dragStarted) {
            longPressTriggered = true;
            sendInput({action: "right_click", ...point});
          }
        }, 650);
      } else if (pointers.size === 2) {
        multiTouchGesture = true;
        if (longPressTimer) clearTimeout(longPressTimer);
        if (dragStarted) sendInput({action: "up", ...lastPointerPosition});
        dragStarted = false;
        longPressTriggered = false;
        oneFingerMode = "pending";
        primaryStart = null;
        contentPoint(event.clientX, event.clientY);
        zoom.beginTwoFinger(pointers);
      }
    });

    screenArea.addEventListener("pointermove", event => {
      if (!pointers.has(event.pointerId)) return;
      event.preventDefault();
      const previous = pointers.get(event.pointerId);
      pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
      if (pointers.size >= 2) {
        if (longPressTimer) clearTimeout(longPressTimer);
        const gesture = zoom.moveTwoFinger(pointers);
        if (gesture.type === "scroll" && gesture.delta) {
          sendInput({action: "scroll", delta: gesture.delta});
        }
        return;
      }
      if (multiTouchGesture) return;
      if (longPressTriggered) return;
      const start = primaryStart || previous;
      if (oneFingerMode === "pending") {
        oneFingerMode = classifyOneFinger(
          event.clientX - start.x,
          event.clientY - start.y
        );
        if (oneFingerMode === "pending") return;
      }
      if (longPressTimer) clearTimeout(longPressTimer);
      if (oneFingerMode === "scroll") {
        const delta = Math.round((event.clientY - previous.y) / 3);
        if (delta) {
          sendInput({
            action: "scroll",
            delta: Math.max(-12, Math.min(12, delta))
          });
        }
        return;
      }
      const point = contentPoint(event.clientX, event.clientY);
      if (!point) return;
      if (!dragStarted) {
        dragStarted = true;
        const startPoint = contentPoint(start.x, start.y) || point;
        sendInput({action: "down", ...startPoint});
      }
      const now = performance.now();
      if (now - lastMoveAt > 45) {
        lastMoveAt = now;
        sendInput({action: "move", ...point});
      }
    });

    function endPointer(event) {
      if (!pointers.has(event.pointerId)) return;
      event.preventDefault();
      if (longPressTimer) clearTimeout(longPressTimer);
      pointers.delete(event.pointerId);
      if (pointers.size < 2) zoom.endTwoFinger();
      if (multiTouchGesture) {
        if (pointers.size === 0) {
          multiTouchGesture = false;
          dragStarted = false;
          longPressTriggered = false;
          oneFingerMode = "pending";
          primaryStart = null;
        }
        return;
      }
      if (oneFingerMode === "scroll") {
        dragStarted = false;
        longPressTriggered = false;
        oneFingerMode = "pending";
        primaryStart = null;
        return;
      }
      const point = contentPoint(event.clientX, event.clientY);
      if (!point || pointers.size > 0) return;
      if (dragStarted) {
        sendInput({action: "up", ...point});
      } else if (!longPressTriggered && event.type !== "pointercancel") {
        const now = performance.now();
        const close = lastTapPosition && Math.hypot(
          point.x - lastTapPosition.x,
          point.y - lastTapPosition.y
        ) < .05;
        if (now - lastTapAt < 330 && close) {
          sendInput({action: "double_click", ...point});
          lastTapAt = 0;
          lastTapPosition = null;
        } else {
          sendInput({action: "click", ...point});
          lastTapAt = now;
          lastTapPosition = point;
        }
      }
      dragStarted = false;
      longPressTriggered = false;
      oneFingerMode = "pending";
      primaryStart = null;
    }

    screenArea.addEventListener("pointerup", endPointer);
    screenArea.addEventListener("pointercancel", endPointer);
    return Object.freeze({
      rightClick() {
        sendInput({action: "right_click", ...lastPointerPosition});
      }
    });
  }

  window.AkshGestures = Object.freeze({classifyOneFinger, create});
})();
