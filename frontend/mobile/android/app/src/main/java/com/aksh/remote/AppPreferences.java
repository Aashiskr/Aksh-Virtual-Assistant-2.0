package com.aksh.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class AppPreferences {
    private static final String STORE = "aksh_remote";
    private static final String DISCOVERY_URL = "discovery_url";
    private static final String URL = "server_url";
    private static final String DEVICE_ID = "device_id";
    private static final String TOKEN = "pairing_token";
    private static final String CAREER_BRIEFING_ENABLED =
            "career_briefing_enabled";
    private static final String KEY_ALIAS = "aksh_remote_pairing_key";
    private static final String ENCRYPTED_PREFIX = "v1:";
    private final SharedPreferences preferences;

    AppPreferences(Context context) {
        preferences = context.getSharedPreferences(STORE, Context.MODE_PRIVATE);
    }

    String serverUrl() {
        return preferences.getString(URL, "");
    }

    String discoveryUrl() {
        return preferences.getString(DISCOVERY_URL, "");
    }

    String token() {
        String stored = preferences.getString(TOKEN, "");
        if (stored == null || stored.isBlank()) {
            return "";
        }
        if (!stored.startsWith(ENCRYPTED_PREFIX)) {
            return stored;
        }
        try {
            String[] parts = stored.substring(ENCRYPTED_PREFIX.length())
                    .split(":", 2);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(
                    Cipher.DECRYPT_MODE,
                    key(),
                    new GCMParameterSpec(128, decode(parts[0]))
            );
            return new String(
                    cipher.doFinal(decode(parts[1])),
                    StandardCharsets.UTF_8
            );
        } catch (Exception exception) {
            return "";
        }
    }

    String deviceId() {
        return preferences.getString(DEVICE_ID, "");
    }

    boolean careerBriefingEnabled() {
        return preferences.getBoolean(CAREER_BRIEFING_ENABLED, false);
    }

    void setCareerBriefingEnabled(boolean enabled) {
        preferences.edit()
                .putBoolean(CAREER_BRIEFING_ENABLED, enabled)
                .apply();
    }

    void save(
            String discoveryUrl,
            String deviceId,
            String serverUrl,
            String token
    ) {
        preferences.edit()
                .putString(DISCOVERY_URL, discoveryUrl)
                .putString(DEVICE_ID, deviceId)
                .putString(URL, serverUrl)
                .putString(TOKEN, encrypt(token))
                .apply();
    }

    private String encrypt(String value) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key());
            return ENCRYPTED_PREFIX
                    + encode(cipher.getIV())
                    + ":"
                    + encode(cipher.doFinal(
                            value.getBytes(StandardCharsets.UTF_8)
                    ));
        } catch (Exception exception) {
            throw new IllegalStateException(
                    "Pairing token securely save nahi hua.",
                    exception
            );
        }
    }

    private SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (!store.containsAlias(KEY_ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_AES,
                    "AndroidKeyStore"
            );
            generator.init(new KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT
                            | KeyProperties.PURPOSE_DECRYPT
            ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(KEY_ALIAS, null);
    }

    private static String encode(byte[] value) {
        return Base64.encodeToString(value, Base64.NO_WRAP);
    }

    private static byte[] decode(String value) {
        return Base64.decode(value, Base64.NO_WRAP);
    }
}
