package com.aksh.remote;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.stream.Collectors;

public final class RemoteScreenActivity extends Activity {
    static final String BASE_URL = "aksh.base_url";
    static final String TOKEN = "aksh.token";
    static final String SESSION_ID = "aksh.screen_session";
    private WebView webView;
    private RemoteScreenDisplayController displayController;
    private String baseUrl = "";
    private String token = "";
    private String sessionId = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_SECURE
        );
        setContentView(R.layout.activity_remote_screen);
        displayController = new RemoteScreenDisplayController(this);
        baseUrl = getIntent().getStringExtra(BASE_URL);
        token = getIntent().getStringExtra(TOKEN);
        sessionId = getIntent().getStringExtra(SESSION_ID);
        if (baseUrl == null || token == null || sessionId == null) {
            finish();
            return;
        }
        configureWebView();
        loadRemoteUi();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        webView = findViewById(R.id.remoteScreenWebView);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        webView.setWebViewClient(new LockedWebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(
                new RemoteScreenBridge(this, baseUrl, token, sessionId),
                "AkshBridge"
        );
    }

    private void loadRemoteUi() {
        try {
            String html = readAsset("remote_screen.html")
                    .replace("{{AKSH_STYLE}}", readAsset("remote_screen.css"))
                    .replace(
                            "{{AKSH_ZOOM_SCRIPT}}",
                            readAsset("remote_screen_zoom.js")
                    )
                    .replace(
                            "{{AKSH_GESTURES_SCRIPT}}",
                            readAsset("remote_screen_gestures.js")
                    )
                    .replace(
                            "{{AKSH_DISPLAY_SCRIPT}}",
                            readAsset("remote_screen_display.js")
                    )
                    .replace("{{AKSH_SCRIPT}}", readAsset("remote_screen.js"));
            webView.loadDataWithBaseURL(
                    baseUrl + "/",
                    html,
                    "text/html",
                    StandardCharsets.UTF_8.name(),
                    null
            );
        } catch (Exception exception) {
            finish();
        }
    }

    private String readAsset(String name) throws Exception {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(getAssets().open(name), StandardCharsets.UTF_8)
        )) {
            return reader.lines().collect(Collectors.joining("\n"));
        }
    }

    void toggleFullscreenLandscape() {
        displayController.toggleFullscreenLandscape();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.removeJavascriptInterface("AkshBridge");
            webView.destroy();
        }
        if (!baseUrl.isBlank() && !sessionId.isBlank()) {
            RemoteScreenSessionCloser.close(baseUrl, token, sessionId);
        }
        super.onDestroy();
    }
}
