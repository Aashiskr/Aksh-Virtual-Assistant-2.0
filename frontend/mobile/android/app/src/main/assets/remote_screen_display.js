(() => {
  "use strict";
  const button = document.getElementById("fullScreenButton");
  let expanded = false;

  button.addEventListener("click", () => {
    expanded = !expanded;
    button.classList.toggle("fullscreen-active", expanded);
    button.setAttribute("aria-pressed", String(expanded));
    button.setAttribute(
      "aria-label",
      expanded ? "Exit fullscreen landscape" : "Enter fullscreen landscape"
    );
    AkshBridge.toggleFullscreenLandscape();
  });
})();
