package com.aksh.remote;

import android.webkit.JavascriptInterface;

import org.json.JSONObject;

final class RemoteScreenBridge {
    private final RemoteScreenActivity activity;
    private final String baseUrl;
    private final String token;
    private volatile String sessionId;

    RemoteScreenBridge(
            RemoteScreenActivity activity,
            String baseUrl,
            String token,
            String sessionId
    ) {
        this.activity = activity;
        this.baseUrl = baseUrl;
        this.token = token;
        this.sessionId = sessionId;
    }

    @JavascriptInterface
    public String configuration() {
        JSONObject value = new JSONObject();
        try {
            value.put("baseUrl", baseUrl);
            value.put("token", token);
            value.put("sessionId", sessionId);
        } catch (Exception ignored) {
            return "{}";
        }
        return value.toString();
    }

    @JavascriptInterface
    public void closeScreen() {
        activity.runOnUiThread(activity::finish);
    }

    @JavascriptInterface
    public void toggleFullscreenLandscape() {
        activity.runOnUiThread(activity::toggleFullscreenLandscape);
    }

    @JavascriptInterface
    public void refreshConnection() {
        activity.refreshRemoteConnection();
    }

    @JavascriptInterface
    public void updateScreenSession(String currentSessionId) {
        if (currentSessionId == null || currentSessionId.isBlank()) {
            return;
        }
        sessionId = currentSessionId;
        activity.updateScreenSession(currentSessionId);
    }
}
