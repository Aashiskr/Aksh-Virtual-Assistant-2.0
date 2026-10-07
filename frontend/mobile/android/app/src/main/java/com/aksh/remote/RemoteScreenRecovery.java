package com.aksh.remote;

import android.app.Activity;

import java.util.concurrent.atomic.AtomicBoolean;

final class RemoteScreenRecovery {
    interface Listener {
        void onRecovered(String baseUrl, String token, String sessionId);
    }

    private final Activity activity;
    private final AtomicBoolean resolving = new AtomicBoolean(false);
    private volatile boolean closed;
    private volatile RemoteApiClient activeClient;

    RemoteScreenRecovery(Activity activity) {
        this.activity = activity;
    }

    void request(Listener listener) {
        if (closed || !resolving.compareAndSet(false, true)) {
            return;
        }
        AppPreferences preferences = new AppPreferences(activity);
        RemoteApiClient client = new RemoteApiClient(
                preferences.discoveryUrl(),
                preferences.deviceId(),
                preferences.serverUrl(),
                preferences.token()
        );
        activeClient = client;
        client.createScreenSession((baseUrl, token, sessionId, error) -> {
            client.close();
            activeClient = null;
            resolving.set(false);
            if (closed && error.isBlank()) {
                RemoteScreenSessionCloser.close(baseUrl, token, sessionId);
                return;
            }
            if (closed || !error.isBlank()) {
                return;
            }
            activity.runOnUiThread(() -> {
                if (!closed && !activity.isFinishing() && !activity.isDestroyed()) {
                    listener.onRecovered(baseUrl, token, sessionId);
                }
            });
        });
    }

    void close() {
        closed = true;
        RemoteApiClient client = activeClient;
        activeClient = null;
        if (client != null) {
            client.close();
        }
    }
}
