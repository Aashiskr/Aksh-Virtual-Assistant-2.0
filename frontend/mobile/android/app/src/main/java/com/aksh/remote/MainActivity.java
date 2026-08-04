package com.aksh.remote;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final int AUDIO_PERMISSION = 41;
    private final AudioRecorder recorder = new AudioRecorder();
    private AppPreferences preferences;
    private RemoteApiClient api;
    private EditText discoveryInput;
    private EditText deviceInput;
    private EditText serverInput;
    private EditText tokenInput;
    private EditText commandInput;
    private Button saveButton;
    private Button micButton;
    private Button sendTextButton;
    private TextView statusText;
    private TextView heardText;
    private TextView reportText;
    private RemoteScreenLauncher remoteScreenLauncher;
    private String pendingTypedCommand = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        preferences = new AppPreferences(this);
        bindViews();
        loadSettings();
        remoteScreenLauncher = new RemoteScreenLauncher(
                this,
                this::saveSettings,
                () -> api
        );
        saveButton.setOnClickListener(view -> saveAndTest());
        micButton.setOnClickListener(view -> toggleRecording());
        sendTextButton.setOnClickListener(view -> sendTextCommand());
        commandInput.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendTextCommand();
                return true;
            }
            return false;
        });
    }

    private void bindViews() {
        discoveryInput = findViewById(R.id.discoveryInput);
        deviceInput = findViewById(R.id.deviceInput);
        serverInput = findViewById(R.id.serverInput);
        tokenInput = findViewById(R.id.tokenInput);
        commandInput = findViewById(R.id.commandInput);
        saveButton = findViewById(R.id.saveButton);
        micButton = findViewById(R.id.micButton);
        sendTextButton = findViewById(R.id.sendTextButton);
        statusText = findViewById(R.id.statusText);
        heardText = findViewById(R.id.heardText);
        reportText = findViewById(R.id.reportText);
    }

    private void loadSettings() {
        discoveryInput.setText(preferences.discoveryUrl());
        deviceInput.setText(preferences.deviceId());
        serverInput.setText(preferences.serverUrl());
        tokenInput.setText(preferences.token());
        rebuildClient();
    }

    private void saveAndTest() {
        if (!saveSettings()) {
            return;
        }
        setStatus("Connecting…", false);
        api.test(listener());
    }

    private boolean saveSettings() {
        String discovery = discoveryInput.getText().toString().trim();
        String deviceId = deviceInput.getText().toString()
                .trim().toLowerCase(Locale.ROOT);
        String server = serverInput.getText().toString().trim();
        String token = tokenInput.getText().toString().trim();
        if (!UrlPolicy.isAllowedSecureUrl(discovery)) {
            toast("Discovery relay secure HTTPS address hona chahiye.");
            return false;
        }
        if (!deviceId.isBlank() && !deviceId.matches("[0-9a-f]{24}")) {
            toast("Valid 24-character Device ID enter karein.");
            return false;
        }
        if (!UrlPolicy.isAllowedSecureUrl(server)) {
            toast("Manual URL secure HTTPS address hona chahiye.");
            return false;
        }
        if (!discovery.isBlank() && deviceId.isBlank()) {
            toast("Discovery relay ke saath Device ID bhi enter karein.");
            return false;
        }
        if (discovery.isBlank() && server.isBlank()) {
            toast("Apna Discovery relay URL ya Manual laptop URL enter karein.");
            return false;
        }
        if (token.length() < 24) {
            toast("Valid pairing token enter karein.");
            return false;
        }
        try {
            preferences.save(discovery, deviceId, server, token);
            rebuildClient();
            return true;
        } catch (RuntimeException exception) {
            toast(exception.getMessage());
            return false;
        }
    }

    private void rebuildClient() {
        if (api != null) {
            api.close();
        }
        api = new RemoteApiClient(
                preferences.discoveryUrl(),
                preferences.deviceId(),
                preferences.serverUrl(),
                preferences.token()
        );
    }

    private void toggleRecording() {
        if (recorder.isRecording()) {
            stopAndSend();
            return;
        }
        if (!saveSettings()) {
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    AUDIO_PERMISSION
            );
            return;
        }
        startRecording();
    }

    private void startRecording() {
        try {
            recorder.start(this);
            micButton.setText(R.string.stop_and_send);
            micButton.setActivated(true);
            sendTextButton.setEnabled(false);
            commandInput.setEnabled(false);
            saveButton.setEnabled(false);
            remoteScreenLauncher.setEnabled(false);
            setStatus("Listening… tap again to send", false);
            heardText.setText(R.string.waiting_for_command);
            reportText.setText(R.string.waiting_for_report);
        } catch (Exception exception) {
            setStatus("Microphone start nahi hua", true);
            toast(exception.getMessage());
        }
    }

    private void stopAndSend() {
        File audio;
        try {
            audio = recorder.stop();
        } catch (RuntimeException exception) {
            recorder.cancel();
            setStatus("Recording bahut short thi. Dobara boliye.", true);
            resetMicButton();
            setCommandControlsEnabled(true);
            return;
        }
        resetMicButton();
        setCommandControlsEnabled(false);
        api.sendAudio(audio, listener());
    }

    private void sendTextCommand() {
        if (recorder.isRecording()) {
            toast("Pehle voice recording stop karein.");
            return;
        }
        String command = commandInput.getText().toString().trim();
        if (command.isBlank()) {
            toast("Aksh ke liye command type karein.");
            return;
        }
        if (!saveSettings()) {
            return;
        }
        pendingTypedCommand = command;
        heardText.setText(getString(R.string.typed_command, command));
        reportText.setText(R.string.waiting_for_report);
        hideKeyboard();
        setCommandControlsEnabled(false);
        api.sendText(command, listener());
    }

    private RemoteApiClient.Listener listener() {
        return (state, heard, report, error) -> runOnUiThread(() -> {
            if (!heard.isBlank()) {
                heardText.setText(getString(R.string.heard_report, heard));
            }
            if (!report.isBlank()) {
                reportText.setText(getString(R.string.completion_report, report));
            }
            boolean failed = "failed".equals(state);
            setStatus(failed ? error : CommandStatusText.forState(state), failed);
            if ("completed".equals(state) || failed) {
                setCommandControlsEnabled(true);
                if ("completed".equals(state)
                        && !pendingTypedCommand.isBlank()) {
                    commandInput.setText("");
                }
                pendingTypedCommand = "";
            }
        });
    }

    private void resetMicButton() {
        micButton.setText(R.string.start_listening);
        micButton.setActivated(false);
    }

    private void setCommandControlsEnabled(boolean enabled) {
        micButton.setEnabled(enabled);
        sendTextButton.setEnabled(enabled);
        commandInput.setEnabled(enabled);
        saveButton.setEnabled(enabled);
        remoteScreenLauncher.setEnabled(enabled);
    }

    private void hideKeyboard() {
        commandInput.clearFocus();
        InputMethodManager keyboard = getSystemService(InputMethodManager.class);
        if (keyboard != null) {
            keyboard.hideSoftInputFromWindow(commandInput.getWindowToken(), 0);
        }
    }

    private void setStatus(String text, boolean error) {
        statusText.setText(text);
        statusText.setTextColor(getColor(
                error ? R.color.error : R.color.success
        ));
    }

    private void toast(String text) {
        Toast.makeText(this, text, Toast.LENGTH_LONG).show();
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults
    ) {
        super.onRequestPermissionsResult(
                requestCode, permissions, grantResults
        );
        if (requestCode == AUDIO_PERMISSION
                && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startRecording();
        } else {
            toast("Phone microphone permission required hai.");
        }
    }

    @Override
    protected void onDestroy() {
        recorder.cancel();
        if (api != null) {
            api.close();
        }
        super.onDestroy();
    }
}
