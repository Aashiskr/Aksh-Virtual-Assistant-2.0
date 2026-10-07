package com.aksh.remote;

import android.os.Build;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;

final class PhoneSigningKey {
    private static final String ALIAS = "aksh_windows_unlock_signing_v1";

    String publicKeyBase64() throws Exception {
        KeyStore store = store();
        if (!store.containsAlias(ALIAS)) {
            create();
            store = store();
        }
        return Base64.encodeToString(
                store.getCertificate(ALIAS).getPublicKey().getEncoded(),
                Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING
        );
    }

    Signature signature() throws Exception {
        KeyStore store = store();
        if (!store.containsAlias(ALIAS)) {
            create();
            store = store();
        }
        PrivateKey key = (PrivateKey) store.getKey(ALIAS, null);
        Signature signature = Signature.getInstance("SHA256withECDSA");
        signature.initSign(key);
        return signature;
    }

    void reset() {
        try {
            KeyStore store = store();
            if (store.containsAlias(ALIAS)) {
                store.deleteEntry(ALIAS);
            }
        } catch (Exception ignored) {
            // A later enrollment attempt will surface a useful error.
        }
    }

    private void create() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_EC,
                "AndroidKeyStore"
        );
        KeyGenParameterSpec.Builder builder =
                new KeyGenParameterSpec.Builder(
                        ALIAS,
                        KeyProperties.PURPOSE_SIGN
                )
                        .setAlgorithmParameterSpec(
                                new ECGenParameterSpec("secp256r1")
                        )
                        .setDigests(KeyProperties.DIGEST_SHA256)
                        .setUserAuthenticationRequired(true)
                        .setInvalidatedByBiometricEnrollment(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            builder.setUserAuthenticationParameters(
                    0,
                    KeyProperties.AUTH_BIOMETRIC_STRONG
            );
        } else {
            builder.setUserAuthenticationValidityDurationSeconds(-1);
        }
        generator.initialize(builder.build());
        generator.generateKeyPair();
    }

    private static KeyStore store() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        return store;
    }
}
