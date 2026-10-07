(() => {
  "use strict";

  const MIN_LEVEL = 1;
  const MAX_LEVEL = 2.5;

  function clampLevel(value) {
    return Math.max(MIN_LEVEL, Math.min(MAX_LEVEL, Number(value) || MIN_LEVEL));
  }

  function anchoredPan({
    panX,
    panY,
    oldLevel,
    newLevel,
    focusX,
    focusY,
    centerX,
    centerY
  }) {
    const previousLevel = Math.max(MIN_LEVEL, Number(oldLevel) || MIN_LEVEL);
    const ratio = clampLevel(newLevel) / previousLevel;
    return {
      x: focusX - centerX - ratio * (focusX - centerX - panX),
      y: focusY - centerY - ratio * (focusY - centerY - panY)
    };
  }

  function create(options) {
    let level = 1;
    let gesture = null;
    let panX = 0;
    let panY = 0;
    let contentBox = null;
    let lastFocus = null;
    const {
      screenArea,
      video,
      frame,
      controls,
      outButton,
      valueButton,
      inButton
    } = options;

    function render() {
      const transform = `translate(${panX}px, ${panY}px) scale(${level})`;
      video.style.transform = transform;
      frame.style.transform = transform;
    }

    function clampPan() {
      if (!contentBox || level <= 1) {
        panX = 0;
        panY = 0;
        return;
      }
      const areaWidth = contentBox.width + contentBox.offsetX * 2;
      const areaHeight = contentBox.height + contentBox.offsetY * 2;
      const maximumX = Math.max(0, (contentBox.width * level - areaWidth) / 2);
      const maximumY = Math.max(0, (contentBox.height * level - areaHeight) / 2);
      panX = Math.max(-maximumX, Math.min(maximumX, panX));
      panY = Math.max(-maximumY, Math.min(maximumY, panY));
    }

    function viewportCenter() {
      const area = screenArea || video.parentElement;
      const rect = area && area.getBoundingClientRect
        ? area.getBoundingClientRect()
        : {left: 0, top: 0, width: 0, height: 0};
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      };
    }

    function set(nextLevel, focus = lastFocus) {
      const previousLevel = level;
      const boundedLevel = clampLevel(nextLevel);
      if (focus && boundedLevel !== previousLevel) {
        const center = viewportCenter();
        const nextPan = anchoredPan({
          panX,
          panY,
          oldLevel: previousLevel,
          newLevel: boundedLevel,
          focusX: focus.x,
          focusY: focus.y,
          centerX: center.x,
          centerY: center.y
        });
        panX = nextPan.x;
        panY = nextPan.y;
      }
      level = boundedLevel;
      clampPan();
      render();
      valueButton.textContent = `${Math.round(level * 100)}%`;
      outButton.disabled = level <= MIN_LEVEL;
      inButton.disabled = level >= MAX_LEVEL;
    }

    function metrics(points) {
      const [first, second] = Array.from(points.values()).slice(0, 2);
      if (!first || !second) return null;
      return {
        distance: Math.hypot(second.x - first.x, second.y - first.y),
        centerX: (first.x + second.x) / 2,
        centerY: (first.y + second.y) / 2
      };
    }

    ["pointerdown", "pointermove", "pointerup", "pointercancel"].forEach(type => {
      controls.addEventListener(type, event => event.stopPropagation());
    });
    outButton.addEventListener("click", () => set(level - .25));
    inButton.addEventListener("click", () => set(level + .25));
    valueButton.addEventListener("click", () => set(1));
    set(1);

    return Object.freeze({
      beginTwoFinger(points) {
        const start = metrics(points);
        if (!start) return;
        lastFocus = {x: start.centerX, y: start.centerY};
        gesture = {
          mode: "pending",
          startDistance: Math.max(1, start.distance),
          startCenterX: start.centerX,
          startPanX: panX,
          startPanY: panY,
          lastCenterX: start.centerX,
          startCenterY: start.centerY,
          lastCenterY: start.centerY,
          startLevel: level
        };
      },
      moveTwoFinger(points) {
        const current = metrics(points);
        if (!gesture || !current) return {type: "pending"};
        const scale = current.distance / gesture.startDistance;
        const distanceChange = Math.abs(scale - 1);
        const horizontalChange = current.centerX - gesture.lastCenterX;
        const centerChange = current.centerY - gesture.startCenterY;
        if (gesture.mode === "pending") {
          if (distanceChange >= .08) gesture.mode = "zoom";
          else if (Math.hypot(horizontalChange, centerChange) >= 9) {
            gesture.mode = level > 1 ? "pan" : "scroll";
          }
        }
        if (gesture.mode === "zoom") {
          const nextLevel = clampLevel(gesture.startLevel * scale);
          const center = viewportCenter();
          const nextPan = anchoredPan({
            panX: gesture.startPanX,
            panY: gesture.startPanY,
            oldLevel: gesture.startLevel,
            newLevel: nextLevel,
            focusX: gesture.startCenterX,
            focusY: gesture.startCenterY,
            centerX: center.x,
            centerY: center.y
          });
          const focusTravelX = current.centerX - gesture.startCenterX;
          const focusTravelY = current.centerY - gesture.startCenterY;
          level = nextLevel;
          panX = nextPan.x + focusTravelX;
          panY = nextPan.y + focusTravelY;
          clampPan();
          render();
          valueButton.textContent = `${Math.round(level * 100)}%`;
          outButton.disabled = level <= MIN_LEVEL;
          inButton.disabled = level >= MAX_LEVEL;
          lastFocus = {x: current.centerX, y: current.centerY};
          gesture.lastCenterX = current.centerX;
          gesture.lastCenterY = current.centerY;
          return {type: "zoom"};
        }
        if (gesture.mode === "pan") {
          panX += current.centerX - gesture.lastCenterX;
          panY += current.centerY - gesture.lastCenterY;
          clampPan();
          render();
          gesture.lastCenterX = current.centerX;
          gesture.lastCenterY = current.centerY;
          return {type: "pan"};
        }
        if (gesture.mode === "scroll") {
          const delta = current.centerY - gesture.lastCenterY;
          gesture.lastCenterY = current.centerY;
          const accelerated = Math.round(delta / 2);
          return {
            type: "scroll",
            delta: Math.max(-12, Math.min(12, accelerated))
          };
        }
        return {type: "pending"};
      },
      endTwoFinger() {
        gesture = null;
      },
      rememberFocus(clientX, clientY) {
        if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) return;
        lastFocus = {x: clientX, y: clientY};
      },
      reset() {
        set(MIN_LEVEL);
      },
      adjustContentBox(box) {
        contentBox = box;
        clampPan();
        const scaledWidth = box.width * level;
        const scaledHeight = box.height * level;
        return {
          width: scaledWidth,
          height: scaledHeight,
          offsetX: box.offsetX - (scaledWidth - box.width) / 2 + panX,
          offsetY: box.offsetY - (scaledHeight - box.height) / 2 + panY
        };
      }
    });
  }

  window.AkshZoom = Object.freeze({anchoredPan, clampLevel, create});
})();
