package com.aksh.remote;

import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

final class LockedWebViewClient extends WebViewClient {
    @Override
    public boolean shouldOverrideUrlLoading(
            WebView view,
            WebResourceRequest request
    ) {
        return true;
    }

    @Override
    @SuppressWarnings("deprecation")
    public boolean shouldOverrideUrlLoading(WebView view, String url) {
        return true;
    }
}
