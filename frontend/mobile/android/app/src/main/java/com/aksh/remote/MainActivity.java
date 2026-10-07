package com.aksh.remote;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.util.Locale;

import org.json.JSONObject;

public final class MainActivity extends Activity {
    private static final int AUDIO_PERMISSION = 41;
    private static final int NOTIFICATION_PERMISSION = 42;
    private static final long MEETING_REFRESH_MILLIS = 5000L;
    private final AudioRecorder recorder = new AudioRecorder();
    private final Handler meetingRefreshHandler = new Handler(
            Looper.getMainLooper()
    );
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
    private Button connectionSettingsButton;
    private Button secureLoginButton;
    private Button careerBriefButton;
    private Switch careerUpdatesSwitch;
    private TextView statusText;
    private TextView heardText;
    private TextView reportText;
    private LinearLayout meetingCard;
    private LinearLayout pairingForm;
    private TextView meetingTitleText;
    private TextView meetingDetailsText;
    private TextView meetingLinkText;
    private Button copyMeetingLinkButton;
    private RemoteScreenLauncher remoteScreenLauncher;
    private SecureRemoteLoginLauncher secureLoginLauncher;
    private String pendingTypedCommand = "";
    private String meetingLink = "";
    private volatile boolean meetingRefreshInFlight;
    private final Runnable meetingRefresh = new Runnable() {
        @Override
        public void run() {
            refreshLatestMeeting();
            meetingRefreshHandler.postDelayed(this, MEETING_REFRESH_MILLIS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        if (
                Build.VERSION.SDK_INT >= 33
                        && checkSelfPermission(
                                Manifest.permission.POST_NOTIFICATIONS
                        ) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(
                    new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    NOTIFICATION_PERMISSION
            );
        }
        preferences = new AppPreferences(this);
        bindViews();
        loadSettings();
        remoteScreenLauncher = new RemoteScreenLauncher(
                this,
                this::saveSettings,
                () -> api
        );
        secureLoginLauncher = new SecureRemoteLoginLauncher(this);
        saveButton.setOnClickListener(view -> saveAndTest());
        connectionSettingsButton.setOnClickListener(
                view -> setPairingFormVisible(
                        pairingForm.getVisibility() != View.VISIBLE
                )
        );
        micButton.setOnClickListener(view -> toggleRecording());
        sendTextButton.setOnClickListener(view -> sendTextCommand());
        secureLoginButton.setOnClickListener(view -> secureLoginLauncher.requestOpen());
        careerBriefButton.setOnClickListener(view -> startActivity(
                new Intent(this, CareerBriefingActivity.class)
        ));
        careerUpdatesSwitch.setOnCheckedChangeListener((view, enabled) -> {
            preferences.setCareerBriefingEnabled(enabled);
            syncCareerBriefing(true);
        });
        copyMeetingLinkButton.setOnClickListener(view -> copyMeetingLink());
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
        connectionSettingsButton = findViewById(R.id.connectionSettingsButton);
        secureLoginButton = findViewById(R.id.secureLoginButton);
        careerBriefButton = findViewById(R.id.careerBriefButton);
        careerUpdatesSwitch = findViewById(R.id.careerUpdatesSwitch);
        statusText = findViewById(R.id.statusText);
        heardText = findViewById(R.id.heardText);
        reportText = findViewById(R.id.reportText);
        meetingCard = findViewById(R.id.meetingCard);
        pairingForm = findViewById(R.id.pairingForm);
        meetingTitleText = findViewById(R.id.meetingTitleText);
        meetingDetailsText = findViewById(R.id.meetingDetailsText);
        meetingLinkText = findViewById(R.id.meetingLinkText);
        copyMeetingLinkButton = findViewById(R.id.copyMeetingLinkButton);
    }

    private void loadSettings() {
        discoveryInput.setText(preferences.discoveryUrl());
        deviceInput.setText(preferences.deviceId());
        serverInput.setText(preferences.serverUrl());
        tokenInput.setText(preferences.token());
        boolean paired = hasSavedConnection();
        setPairingFormVisible(!paired);
        if (paired) {
            setStatus(getString(R.string.paired_ready), false);
        }
        careerUpdatesSwitch.setChecked(preferences.careerBriefingEnabled());
        rebuildClient();
        LaptopWakeMonitor.sync(this);
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) {
            CareerBriefingMessagingService.createChannel(manager);
        }
        syncCareerBriefing(false);
    }

    private void saveAndTest() {
        if (!saveSettings()) {
            return;
        }
        setPairingFormVisible(false);
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
            LaptopWakeMonitor.sync(this);
            syncCareerBriefing(false);
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
        meetingRefreshInFlight = false;
        api = new RemoteApiClient(
                preferences.discoveryUrl(),
                preferences.deviceId(),
                preferences.serverUrl(),
                preferences.token()
        );
    }

    private void syncCareerBriefing(boolean showResult) {
        CareerBriefingManager.sync(this, (ok, message) -> runOnUiThread(() -> {
            if (showResult
                    || (!ok && preferences.careerBriefingEnabled())) {
                toast(message);
            }
        }));
    }

    private boolean hasSavedConnection() {
        boolean hasAddress = !preferences.discoveryUrl().isBlank()
                || !preferences.serverUrl().isBlank();
        return hasAddress && preferences.token().length() >= 24;
    }

    private void setPairingFormVisible(boolean visible) {
        pairingForm.setVisibility(visible ? View.VISIBLE : View.GONE);
        connectionSettingsButton.setText(
                visible
                        ? R.string.connection_settings_hide
                        : R.string.connection_settings_show
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
        return (state, heard, report, error, meeting) -> runOnUiThread(() -> {
            if (!heard.isBlank()) {
                heardText.setText(getString(R.string.heard_report, heard));
            }
            if (!report.isBlank()) {
                reportText.setText(getString(R.string.completion_report, report));
            }
            if (meeting != null) {
                showMeeting(meeting);
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

    private void showMeeting(JSONObject meeting) {
        meetingLink = meeting.optString("link", "").trim();
        if (meetingLink.isBlank()) {
            return;
        }
        String title = meeting.optString(
                "title", getString(R.string.meeting_default_title)
        );
        String when = meeting.optString(
                "scheduled_for", meeting.optString("time", "")
        );
        String account = meeting.optString("account_email", "").trim();
        if (account.isBlank()) {
            account = meeting.optString("account", "");
        }
        meetingTitleText.setText(title);
        meetingDetailsText.setText(
                getString(R.string.meeting_details, when, account)
        );
        meetingLinkText.setText(meetingLink);
        copyMeetingLinkButton.setEnabled(true);
        meetingCard.setVisibility(View.VISIBLE);
    }

    private void copyMeetingLink() {
        if (meetingLink.isBlank()) {
            return;
        }
        ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        if (clipboard == null) {
            toast(getString(R.string.meeting_copy_failed));
            return;
        }
        clipboard.setPrimaryClip(
                ClipData.newPlainText("Google Meet link", meetingLink)
        );
        toast(getString(R.string.meeting_link_copied));
    }

    private void refreshLatestMeeting() {
        if (
                api == null
                        || preferences == null
                        || preferences.token().length() < 24
                        || meetingRefreshInFlight
        ) {
            return;
        }
        meetingRefreshInFlight = true;
        api.fetchLatestMeeting(meeting -> {
            meetingRefreshInFlight = false;
            if (meeting != null) {
                runOnUiThread(() -> showMeeting(meeting));
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
        connectionSettingsButton.setEnabled(enabled);
        discoveryInput.setEnabled(enabled);
        deviceInput.setEnabled(enabled);
        serverInput.setEnabled(enabled);
        tokenInput.setEnabled(enabled);
        remoteScreenLauncher.setEnabled(enabled);
        secureLoginButton.setEnabled(enabled);
        careerBriefButton.setEnabled(enabled);
        careerUpdatesSwitch.setEnabled(enabled);
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
        if (requestCode == NOTIFICATION_PERMISSION) {
            if (
                    grantResults.length > 0
                            && grantResults[0]
                            == PackageManager.PERMISSION_GRANTED
            ) {
                LaptopWakeMonitor.sync(this);
                syncCareerBriefing(false);
            } else {
                toast(
                        getString(
                                R.string.laptop_wake_action_failed
                        )
                );
            }
            return;
        }
        if (requestCode == AUDIO_PERMISSION
                && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startRecording();
        } else {
            toast("Phone microphone permission required hai.");
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        meetingRefreshHandler.removeCallbacks(meetingRefresh);
        meetingRefreshHandler.post(meetingRefresh);
    }

    @Override
    protected void onPause() {
        meetingRefreshHandler.removeCallbacks(meetingRefresh);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        meetingRefreshHandler.removeCallbacks(meetingRefresh);
        recorder.cancel();
        if (secureLoginLauncher != null) {
            secureLoginLauncher.close();
        }
        if (api != null) {
            api.close();
        }
        super.onDestroy();
    }
}
