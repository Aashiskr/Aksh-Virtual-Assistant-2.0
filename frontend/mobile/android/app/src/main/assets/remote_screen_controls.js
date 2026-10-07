(function (root) {
  "use strict";

  const SCROLL_STEP = 6;

  function scrollPayload(direction) {
    const normalized = String(direction || "").trim().toLowerCase();
    if (normalized === "up") {
      return {action: "scroll", delta: SCROLL_STEP};
    }
    if (normalized === "down") {
      return {action: "scroll", delta: -SCROLL_STEP};
    }
    throw new Error("Unsupported scroll direction");
  }

  function bind(documentRef, sendInput) {
    documentRef.querySelectorAll("[data-scroll]").forEach(button => {
      button.addEventListener("click", () => {
        sendInput(scrollPayload(button.dataset.scroll));
      });
    });
  }

  root.AkshRemoteControls = {SCROLL_STEP, scrollPayload, bind};
})(typeof window !== "undefined" ? window : globalThis);
