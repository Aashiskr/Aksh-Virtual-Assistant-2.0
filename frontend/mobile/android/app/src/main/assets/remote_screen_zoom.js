(() => {
  "use strict";

  function create(options) {
    let level = 1;
    let gesture = null;
    let panX = 0;
    let panY = 0;
    let contentBox = null;
    const {
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

    function set(nextLevel) {
      level = Math.max(1, Math.min(2.5, nextLevel));
      clampPan();
      render();
      valueButton.textContent = `${Math.round(level * 100)}%`;
      outButton.disabled = level <= 1;
      inButton.disabled = level >= 2.5;
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
        gesture = {
          mode: "pending",
          startDistance: Math.max(1, start.distance),
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
          set(gesture.startLevel * scale);
          panX += current.centerX - gesture.lastCenterX;
          panY += current.centerY - gesture.lastCenterY;
          clampPan();
          render();
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

  window.AkshZoom = Object.freeze({create});
})();
