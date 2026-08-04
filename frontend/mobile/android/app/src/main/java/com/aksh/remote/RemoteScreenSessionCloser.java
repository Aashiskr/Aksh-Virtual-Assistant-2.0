package com.aksh.remote;

import java.net.HttpURLConnection;
import java.net.URL;

final class RemoteScreenSessionCloser {
    private RemoteScreenSessionCloser() {
    }

    static void close(String baseUrl, String token, String sessionId) {
        Thread thread = new Thread(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(
                        baseUrl + "/v1/screen/sessions/current"
                ).openConnection();
                connection.setRequestMethod("DELETE");
                connection.setConnectTimeout(4000);
                connection.setReadTimeout(4000);
                connection.setRequestProperty("Authorization", "Bearer " + token);
                connection.setRequestProperty(
                        "X-Aksh-Screen-Session", sessionId
                );
                connection.getResponseCode();
            } catch (Exception ignored) {
                // Session expires automatically if the laptop is unreachable.
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }
        }, "aksh-screen-close");
        thread.start();
    }
}
