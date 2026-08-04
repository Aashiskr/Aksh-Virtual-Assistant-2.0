package com.aksh.remote;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class DiscoveryClient {
    private final String discoveryUrl;
    private final String deviceId;
    private final String token;

    DiscoveryClient(String discoveryUrl, String deviceId, String token) {
        this.discoveryUrl = trimSlashes(discoveryUrl);
        this.deviceId = deviceId;
        this.token = token;
    }

    String resolve() throws Exception {
        URL endpoint = new URL(
                discoveryUrl + "/v1/devices/" + deviceId
        );
        HttpURLConnection connection =
                (HttpURLConnection) endpoint.openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(20000);
        connection.setRequestProperty(
                "Authorization", "Bearer " + token
        );
        connection.setRequestProperty("Accept", "application/json");

        int status = connection.getResponseCode();
        JSONObject response = readJson(connection, status);
        if (status >= 400) {
            throw new IllegalStateException(
                    response.optString(
                            "error",
                            response.optString("detail", "Discovery failed")
                    )
            );
        }
        String url = trimSlashes(response.optString("url", ""));
        if (!url.startsWith("https://")) {
            throw new IllegalStateException(
                    "Laptop ka secure internet URL available nahi hai."
            );
        }
        return url;
    }

    private static JSONObject readJson(
            HttpURLConnection connection, int status
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

    private static String trimSlashes(String value) {
        return value == null ? "" : value.replaceAll("/+$", "");
    }
}
