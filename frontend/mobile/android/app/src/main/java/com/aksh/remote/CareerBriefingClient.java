package com.aksh.remote;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class CareerBriefingClient {
    interface Listener {
        void onResult(JSONObject response, String error);
    }

    private final String endpoint;
    private final String token;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    CareerBriefingClient(
            String discoveryUrl,
            String deviceId,
            String token
    ) {
        this.endpoint = trimSlashes(discoveryUrl)
                + "/v1/devices/"
                + deviceId
                + "/briefing";
        this.token = token;
    }

    void register(String fcmToken, boolean enabled, Listener listener) {
        executor.execute(() -> {
            try {
                JSONObject profile = new JSONObject();
                profile.put("course", "B.Tech");
                profile.put("year", 4);
                profile.put("branch", "all");
                profile.put("regions", new JSONArray()
                        .put("Uttar Pradesh")
                        .put("Bihar")
                        .put("All India"));
                profile.put("timezone", "Asia/Kolkata");
                profile.put("delivery_hour", 11);

                JSONObject body = new JSONObject();
                body.put("enabled", enabled);
                body.put("fcm_token", enabled ? fcmToken : "");
                body.put("profile", profile);
                listener.onResult(
                        request(
                                endpoint,
                                "PUT",
                                body.toString().getBytes(StandardCharsets.UTF_8)
                        ),
                        ""
                );
            } catch (Exception exception) {
                listener.onResult(null, cleanError(exception));
            }
        });
    }

    void latest(Listener listener) {
        executor.execute(() -> {
            try {
                listener.onResult(
                        request(endpoint + "/latest", "GET", null),
                        ""
                );
            } catch (Exception exception) {
                listener.onResult(null, cleanError(exception));
            }
        });
    }

    void sendTest(Listener listener) {
        executor.execute(() -> {
            try {
                listener.onResult(
                        request(endpoint + "/test", "POST", new byte[0]),
                        ""
                );
            } catch (Exception exception) {
                listener.onResult(null, cleanError(exception));
            }
        });
    }

    void close() {
        executor.shutdownNow();
    }

    private JSONObject request(
            String url,
            String method,
            byte[] body
    ) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url)
                .openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(30000);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/json");
        if (body != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty(
                    "Content-Type",
                    "application/json; charset=utf-8"
            );
            if (body.length > 0) {
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(body);
                }
            }
        }

        int status = connection.getResponseCode();
        InputStream stream = status >= 400
                ? connection.getErrorStream()
                : connection.getInputStream();
        StringBuilder text = new StringBuilder();
        if (stream != null) {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(stream, StandardCharsets.UTF_8)
            )) {
                String line;
                while ((line = reader.readLine()) != null) {
                    text.append(line);
                }
            }
        }
        JSONObject response = text.length() == 0
                ? new JSONObject()
                : new JSONObject(text.toString());
        if (status >= 400) {
            throw new IllegalStateException(
                    response.optString("detail", "HTTP " + status)
            );
        }
        return response;
    }

    private static String cleanError(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.isBlank()
                ? exception.getClass().getSimpleName()
                : message;
    }

    private static String trimSlashes(String value) {
        return value == null ? "" : value.replaceAll("/+$", "");
    }
}
