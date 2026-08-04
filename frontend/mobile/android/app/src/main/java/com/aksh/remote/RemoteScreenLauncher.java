package com.aksh.remote;

import android.app.Activity;
import android.content.Intent;
import android.widget.Button;
import android.widget.Toast;

import java.util.function.BooleanSupplier;
import java.util.function.Supplier;

final class RemoteScreenLauncher {
    private final Activity activity;
    private final Button button;
    private final BooleanSupplier saveSettings;
    private final Supplier<RemoteApiClient> client;

    RemoteScreenLauncher(
            Activity activity,
            BooleanSupplier saveSettings,
            Supplier<RemoteApiClient> client
    ) {
        this.activity = activity;
        this.saveSettings = saveSettings;
        this.client = client;
        this.button = activity.findViewById(R.id.remoteScreenButton);
        this.button.setOnClickListener(view -> open());
    }

    void setEnabled(boolean enabled) {
        button.setEnabled(enabled);
    }

    private void open() {
        if (!saveSettings.getAsBoolean()) {
            return;
        }
        button.setEnabled(false);
        button.setText(R.string.remote_screen_connecting);
        client.get().createScreenSession(
                (baseUrl, token, sessionId, error) -> activity.runOnUiThread(() -> {
                    button.setEnabled(true);
                    button.setText(R.string.remote_screen_button);
                    if (!error.isBlank()) {
                        Toast.makeText(activity, error, Toast.LENGTH_LONG).show();
                        return;
                    }
                    Intent intent = new Intent(activity, RemoteScreenActivity.class);
                    intent.putExtra(RemoteScreenActivity.BASE_URL, baseUrl);
                    intent.putExtra(RemoteScreenActivity.TOKEN, token);
                    intent.putExtra(RemoteScreenActivity.SESSION_ID, sessionId);
                    activity.startActivity(intent);
                })
        );
    }
}
