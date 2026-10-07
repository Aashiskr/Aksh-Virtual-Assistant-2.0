package com.aksh.remote;

import android.app.Activity;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.security.keystore.KeyPermanentlyInvalidatedException;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;

import java.security.Signature;

public final class UnlockActivity extends Activity {
    private UnlockApiClient client;
    private PhoneSigningKey signingKey;
    private CancellationSignal cancellationSignal;
    private TextView status;
    private TextView detail;
    private Button retry;
    private View progress;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        } else {
            getWindow().addFlags(
                    WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                            | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            );
        }
        setContentView(R.layout.activity_unlock);
        client = new UnlockApiClient(this);
        signingKey = new PhoneSigningKey();
        status = findViewById(R.id.unlockStatus);
        detail = findViewById(R.id.unlockDetail);
        retry = findViewById(R.id.unlockRetry);
        progress = findViewById(R.id.unlockProgress);
        retry.setOnClickListener(view -> begin());
        findViewById(R.id.unlockCancel).setOnClickListener(view -> finish());
        begin();
    }

    private void begin() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            showError("Phone unlock requires Android 9 or newer.");
            return;
        }
        retry.setVisibility(View.GONE);
        progress.setVisibility(View.VISIBLE);
        status.setText(R.string.unlock_contacting_laptop);
        detail.setText(R.string.unlock_contacting_detail);
        try {
            client.prepare(
                    signingKey.publicKeyBase64(),
                    new UnlockApiClient.PrepareListener() {
                        @Override
                        public void onReady(
                                UnlockApiClient.Challenge challenge
                        ) {
                            showBiometric(challenge);
                        }

                        @Override
                        public void onError(String error) {
                            showError(error);
                        }
                    }
            );
        } catch (Exception exception) {
            showError(cleanError(exception));
        }
    }

    private void showBiometric(UnlockApiClient.Challenge challenge) {
        status.setText(R.string.unlock_touch_sensor);
        detail.setText(R.string.unlock_biometric_detail);
        progress.setVisibility(View.GONE);
        try {
            Signature signature = signingKey.signature();
            BiometricPrompt.Builder builder =
                    new BiometricPrompt.Builder(this)
                            .setTitle(getString(R.string.unlock_prompt_title))
                            .setSubtitle(
                                    getString(R.string.unlock_prompt_subtitle)
                            )
                            .setDescription(
                                    getString(R.string.unlock_prompt_description)
                            )
                            .setNegativeButton(
                                    getString(R.string.cancel),
                                    getMainExecutor(),
                                    (dialog, which) -> finish()
                            );
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                builder.setAllowedAuthenticators(
                        android.hardware.biometrics.BiometricManager
                                .Authenticators.BIOMETRIC_STRONG
                );
            }
            cancellationSignal = new CancellationSignal();
            builder.build().authenticate(
                    new BiometricPrompt.CryptoObject(signature),
                    cancellationSignal,
                    getMainExecutor(),
                    new BiometricPrompt.AuthenticationCallback() {
                        @Override
                        public void onAuthenticationSucceeded(
                                BiometricPrompt.AuthenticationResult result
                        ) {
                            signAndApprove(result, challenge);
                        }

                        @Override
                        public void onAuthenticationFailed() {
                            status.setText(
                                    R.string.unlock_fingerprint_not_recognized
                            );
                        }

                        @Override
                        public void onAuthenticationError(
                                int errorCode,
                                CharSequence errorString
                        ) {
                            if (
                                    errorCode
                                            != BiometricPrompt
                                            .BIOMETRIC_ERROR_USER_CANCELED
                            ) {
                                showError(errorString.toString());
                            }
                        }
                    }
            );
        } catch (KeyPermanentlyInvalidatedException exception) {
            signingKey.reset();
            showError(
                    "Your phone biometrics changed. Reset phone enrollment "
                            + "on the laptop, then try again."
            );
        } catch (Exception exception) {
            showError(cleanError(exception));
        }
    }

    private void signAndApprove(
            BiometricPrompt.AuthenticationResult result,
            UnlockApiClient.Challenge challenge
    ) {
        try {
            BiometricPrompt.CryptoObject cryptoObject =
                    result.getCryptoObject();
            if (cryptoObject == null || cryptoObject.getSignature() == null) {
                throw new IllegalStateException(
                        "Android did not return the protected signing key."
                );
            }
            Signature signature = cryptoObject.getSignature();
            signature.update(challenge.payload);
            byte[] signed = signature.sign();
            status.setText(R.string.unlock_approved);
            detail.setText(R.string.unlock_sending_approval);
            progress.setVisibility(View.VISIBLE);
            client.approve(
                    challenge,
                    signed,
                    new UnlockApiClient.ApprovalListener() {
                        @Override
                        public void onApproved() {
                            progress.setVisibility(View.GONE);
                            status.setText(R.string.unlock_success);
                            detail.setText(R.string.unlock_success_detail);
                            getWindow().getDecorView().postDelayed(
                                    UnlockActivity.this::finish,
                                    1400
                            );
                        }

                        @Override
                        public void onError(String error) {
                            showError(error);
                        }
                    }
            );
        } catch (Exception exception) {
            showError(cleanError(exception));
        }
    }

    private void showError(String error) {
        progress.setVisibility(View.GONE);
        status.setText(R.string.unlock_not_completed);
        detail.setText(error);
        retry.setVisibility(View.VISIBLE);
    }

    private static String cleanError(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.isBlank()
                ? "Phone fingerprint approval could not be started."
                : message;
    }

    @Override
    protected void onDestroy() {
        if (cancellationSignal != null) {
            cancellationSignal.cancel();
        }
        if (client != null) {
            client.close();
        }
        super.onDestroy();
    }
}
