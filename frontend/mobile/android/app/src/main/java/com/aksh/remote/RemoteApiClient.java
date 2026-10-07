package com.aksh.remote;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class RemoteApiClient {
    interface Listener {
        void onUpdate(
                String state,
                String heard,
                String report,
                String error,
                JSONObject meeting
        );
    }

    interface ScreenSessionListener {
        void onReady(String baseUrl, String token, String sessionId, String error);
    }

    interface MeetingListener {
        void onResult(JSONObject meeting);
    }

    private final String manualUrl;
    private final DiscoveryClient discovery;
    private final String token;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    RemoteApiClient(
            String discoveryUrl,
            String deviceId,
            String manualUrl,
            String token
    ) {
        this.manualUrl = UrlPolicy.isAllowedSecureUrl(manualUrl)
                ? trimSlashes(manualUrl)
                : "";
        this.discovery = discoveryUrl.isBlank() || deviceId.isBlank()
                ? null
                : new DiscoveryClient(discoveryUrl, deviceId, token);
        this.token = token;
    }

    void test(Listener listener) {
        executor.execute(() -> {
            Exception lastError = null;
            for (int attempt = 0; attempt < 6; attempt++) {
                try {
                    listener.onUpdate("resolving", "", "", "", null);
                    String baseUrl = resolveBaseUrl();
                    JSONObject response = request(
                            baseUrl, "GET", "/v1/health", null, null
                    );
                    listener.onUpdate(
                            "connected",
                            "",
                            "Connected to "
                                    + response.optString("assistant", "Aksh"),
                            "",
                            null
                    );
                    return;
                } catch (Exception exception) {
                    lastError = exception;
                    if (attempt < 5) {
                        try {
                            Thread.sleep(2500);
                        } catch (InterruptedException interrupted) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                    }
                }
            }
            listener.onUpdate("failed", "", "", cleanError(lastError), null);
        });
    }

    void sendAudio(File audio, Listener listener) {
        executor.execute(() -> {
            try {
                listener.onUpdate("resolving", "", "", "", null);
                String baseUrl = resolveBaseUrl();
                listener.onUpdate("uploading", "", "", "", null);
                String jobId = upload(baseUrl, audio);
                poll(baseUrl, jobId, listener);
            } catch (Exception exception) {
                listener.onUpdate("failed", "", "", cleanError(exception), null);
            } finally {
                audio.delete();
            }
        });
    }

    void sendText(String command, Listener listener) {
        executor.execute(() -> {
            try {
                listener.onUpdate("resolving", command, "", "", null);
                String baseUrl = resolveBaseUrl();
                listener.onUpdate("sending_text", command, "", "", null);
                JSONObject payload = new JSONObject();
                payload.put("text", command);
                JSONObject response = request(
                        baseUrl,
                        "POST",
                        "/v1/commands/text",
                        "application/json; charset=utf-8",
                        payload.toString().getBytes(StandardCharsets.UTF_8)
                );
                poll(baseUrl, response.getString("job_id"), listener);
            } catch (Exception exception) {
                listener.onUpdate(
                        "failed", command, "", cleanError(exception), null
                );
            }
        });
    }

    void createScreenSession(ScreenSessionListener listener) {
        executor.execute(() -> {
            try {
                String baseUrl = resolveBaseUrl();
                JSONObject response = request(
                        baseUrl,
                        "POST",
                        "/v1/screen/sessions",
                        "application/json; charset=utf-8",
                        "{}".getBytes(StandardCharsets.UTF_8)
                );
                listener.onReady(
                        baseUrl,
                        token,
                        response.getString("session_id"),
                        ""
                );
            } catch (Exception exception) {
                listener.onReady("", "", "", cleanError(exception));
            }
        });
    }

    void fetchLatestMeeting(MeetingListener listener) {
        executor.execute(() -> {
            try {
                String baseUrl = resolveBaseUrl();
                JSONObject meeting = request(
                        baseUrl,
                        "GET",
                        "/v1/meetings/latest",
                        null,
                        null
                );
                listener.onResult(meeting);
            } catch (Exception ignored) {
                listener.onResult(null);
            }
        });
    }

    void close() {
        executor.shutdownNow();
    }

    private String upload(String baseUrl, File audio) throws Exception {
        String boundary = "Aksh-" + UUID.randomUUID();
        HttpURLConnection connection = open(
                baseUrl,
                "/v1/commands/audio",
                "POST",
                "multipart/form-data; boundary=" + boundary
        );
        try (DataOutputStream output = new DataOutputStream(
                connection.getOutputStream()
        ); FileInputStream input = new FileInputStream(audio)) {
            output.writeBytes("--" + boundary + "\r\n");
            output.writeBytes(
                    "Content-Disposition: form-data; name=\"audio\"; "
                            + "filename=\"command.m4a\"\r\n"
            );
            output.writeBytes("Content-Type: audio/mp4\r\n\r\n");
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                output.write(buffer, 0, count);
            }
            output.writeBytes("\r\n--" + boundary + "--\r\n");
        }
        JSONObject response = readJson(connection);
        return response.getString("job_id");
    }

    private void poll(
            String baseUrl, String jobId, Listener listener
    ) throws Exception {
        for (int attempt = 0; attempt < 120; attempt++) {
            JSONObject job = request(
                    baseUrl,
                    "GET",
                    "/v1/commands/" + jobId,
                    null,
                    null
            );
            String state = job.optString("state", "processing");
            String heard = job.optString("heard", "");
            String report = job.optString("report", "");
            String error = job.optString("error", "");
            JSONObject meeting = job.optJSONObject("meeting");
            listener.onUpdate(state, heard, report, error, meeting);
            if ("completed".equals(state) || "failed".equals(state)) {
                return;
            }
            Thread.sleep(1000);
        }
        throw new IllegalStateException("Aksh response timeout.");
    }

    private JSONObject request(
            String baseUrl,
            String method,
            String path,
            String contentType,
            byte[] body
    ) throws Exception {
        HttpURLConnection connection = open(
                baseUrl, path, method, contentType
        );
        if (body != null) {
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }
        }
        return readJson(connection);
    }

    private HttpURLConnection open(
            String baseUrl,
            String path,
            String method,
            String contentType
    ) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(
                baseUrl + path
        ).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(95000);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/json");
        if (contentType != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", contentType);
        }
        return connection;
    }

    private String resolveBaseUrl() throws Exception {
        Exception discoveryError = null;
        if (discovery != null) {
            try {
                return discovery.resolve();
            } catch (Exception exception) {
                discoveryError = exception;
            }
        }
        if (!manualUrl.isBlank()) {
            return manualUrl;
        }
        if (discoveryError != null) {
            throw discoveryError;
        }
        throw new IllegalStateException(
                "Device ID ya manual laptop URL required hai."
        );
    }

    private JSONObject readJson(HttpURLConnection connection) throws Exception {
        int status = connection.getResponseCode();
        InputStream stream = status >= 400
                ? connection.getErrorStream()
                : connection.getInputStream();
        StringBuilder text = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8)
        )) {
            String line;
            while ((line = reader.readLine()) != null) {
                text.append(line);
            }
        }
        JSONObject json = new JSONObject(text.toString());
        if (status >= 400) {
            throw new IllegalStateException(
                    json.optString("detail", "HTTP " + status)
            );
        }
        return json;
    }

    private static String cleanError(Exception exception) {
        if (exception == null) {
            return "Connection failed.";
        }
        String message = exception.getMessage();
        return message == null || message.isBlank()
                ? exception.getClass().getSimpleName()
                : message;
    }

    private static String trimSlashes(String value) {
        return value == null ? "" : value.replaceAll("/+$", "");
    }
}
