package com.aksh.remote;

import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class UnlockApiClient {
    interface PrepareListener {
        void onReady(Challenge challenge);
        void onError(String error);
    }

    interface ApprovalListener {
        void onApproved();
        void onError(String error);
    }

    static final class Challenge {
        final String baseUrl;
        final String id;
        final byte[] payload;

        Challenge(String baseUrl, String id, byte[] payload) {
            this.baseUrl = baseUrl;
            this.id = id;
            this.payload = payload;
        }
    }

    private final AppPreferences preferences;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    UnlockApiClient(Context context) {
        preferences = new AppPreferences(context);
    }

    void prepare(String publicKey, PrepareListener listener) {
        executor.execute(() -> {
            try {
                Challenge challenge = prepareWithFallback(publicKey);
                main.post(() -> listener.onReady(challenge));
            } catch (Exception exception) {
                String error = cleanError(exception);
                main.post(() -> listener.onError(error));
            }
        });
    }

    void approve(
            Challenge challenge,
            byte[] signature,
            ApprovalListener listener
    ) {
        executor.execute(() -> {
            try {
                JSONObject payload = new JSONObject();
                payload.put("challenge_id", challenge.id);
                payload.put(
                        "signature",
                        Base64.encodeToString(
                                signature,
                                Base64.URL_SAFE
                                        | Base64.NO_WRAP
                                        | Base64.NO_PADDING
                        )
                );
                request(
                        challenge.baseUrl,
                        "POST",
                        "/v1/unlock/approve",
                        payload
                );
                main.post(listener::onApproved);
            } catch (Exception exception) {
                String error = cleanError(exception);
                main.post(() -> listener.onError(error));
            }
        });
    }

    JSONObject healthSync() throws Exception {
        Exception lastError = null;
        for (String baseUrl : resolveBaseUrls()) {
            try {
                return request(baseUrl, "GET", "/v1/health", null);
            } catch (Exception exception) {
                lastError = exception;
            }
        }
        if (lastError != null) {
            throw lastError;
        }
        throw new IllegalStateException(
                "Pair the Aksh app with your laptop first."
        );
    }

    void close() {
        executor.shutdownNow();
    }

    private Challenge prepareWithFallback(String publicKey) throws Exception {
        Exception lastError = null;
        for (String baseUrl : resolveBaseUrls()) {
            try {
                JSONObject enrollment = new JSONObject();
                enrollment.put("public_key", publicKey);
                enrollment.put(
                        "device_label",
                        Build.MANUFACTURER + " " + Build.MODEL
                );
                request(
                        baseUrl,
                        "POST",
                        "/v1/unlock/enroll",
                        enrollment
                );
                JSONObject value = request(
                        baseUrl,
                        "POST",
                        "/v1/unlock/challenge",
                        null
                );
                return new Challenge(
                        baseUrl,
                        value.getString("challenge_id"),
                        Base64.decode(
                                value.getString("payload"),
                                Base64.URL_SAFE
                                        | Base64.NO_WRAP
                                        | Base64.NO_PADDING
                        )
                );
            } catch (Exception exception) {
                lastError = exception;
            }
        }
        if (lastError != null) {
            throw lastError;
        }
        throw new IllegalStateException(
                "Pair the Aksh app with your laptop first."
        );
    }

    private List<String> resolveBaseUrls() throws Exception {
        ArrayList<String> urls = new ArrayList<>();
        String token = preferences.token();
        String discovery = preferences.discoveryUrl();
        String deviceId = preferences.deviceId();
        Exception discoveryError = null;
        if (!discovery.isBlank() && !deviceId.isBlank()) {
            try {
                addUrl(
                        urls,
                        trimSlashes(
                        new DiscoveryClient(
                                discovery,
                                deviceId,
                                token
                        ).resolve()
                        )
                );
            } catch (Exception exception) {
                discoveryError = exception;
            }
        }
        String manual = preferences.serverUrl();
        if (UrlPolicy.isAllowedSecureUrl(manual)) {
            addUrl(urls, trimSlashes(manual));
        }
        if (!urls.isEmpty()) {
            return urls;
        }
        if (discoveryError != null) {
            throw discoveryError;
        }
        throw new IllegalStateException(
                "Pair the Aksh app with your laptop first."
        );
    }

    private static void addUrl(ArrayList<String> urls, String value) {
        if (!value.isBlank() && !urls.contains(value)) {
            urls.add(value);
        }
    }

    private JSONObject request(
            String baseUrl,
            String method,
            String path,
            JSONObject payload
    ) throws Exception {
        HttpURLConnection connection =
                (HttpURLConnection) new URL(baseUrl + path).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setConnectTimeout(12000);
            connection.setReadTimeout(20000);
            connection.setRequestProperty(
                    "Authorization",
                    "Bearer " + preferences.token()
            );
            connection.setRequestProperty("Accept", "application/json");
            if (payload != null) {
                byte[] body =
                        payload.toString().getBytes(StandardCharsets.UTF_8);
                connection.setDoOutput(true);
                connection.setRequestProperty(
                        "Content-Type",
                        "application/json; charset=utf-8"
                );
                connection.setFixedLengthStreamingMode(body.length);
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(body);
                }
            }
            int status = connection.getResponseCode();
            JSONObject response = readJson(connection, status);
            if (status >= 400) {
                throw new IllegalStateException(
                        response.optString(
                                "detail",
                                "Laptop unlock request failed."
                        )
                );
            }
            return response;
        } finally {
            connection.disconnect();
        }
    }

    private static JSONObject readJson(
            HttpURLConnection connection,
            int status
    ) throws Exception {
        InputStream stream = status >= 400
                ? connection.getErrorStream()
                : connection.getInputStream();
        if (stream == null) {
            return new JSONObject();
        }
        StringBuilder text = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8)
        )) {
            String line;
            while ((line = reader.readLine()) != null) {
                text.append(line);
            }
        }
        return text.length() == 0
                ? new JSONObject()
                : new JSONObject(text.toString());
    }

    private static String cleanError(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.isBlank()
                ? "Could not reach your laptop securely."
                : message;
    }

    private static String trimSlashes(String value) {
        return value == null ? "" : value.replaceAll("/+$", "");
    }
}
