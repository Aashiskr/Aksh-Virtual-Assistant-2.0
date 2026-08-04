import assert from "node:assert/strict";
import test from "node:test";

globalThis.window = {};
await import("./app/src/main/assets/remote_screen_gestures.js");

const {classifyOneFinger} = window.AkshGestures;

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
