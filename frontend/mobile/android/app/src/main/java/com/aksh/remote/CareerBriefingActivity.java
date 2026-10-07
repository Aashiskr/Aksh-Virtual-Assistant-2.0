package com.aksh.remote;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Locale;

public final class CareerBriefingActivity extends Activity {
    private TextView status;
    private LinearLayout items;
    private Button refresh;
    private Button test;
    private CareerBriefingClient client;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_career_briefing);
        status = findViewById(R.id.careerBriefStatus);
        items = findViewById(R.id.careerBriefItems);
        refresh = findViewById(R.id.refreshCareerBriefButton);
        test = findViewById(R.id.testCareerNotificationButton);
        Button back = findViewById(R.id.closeCareerBriefButton);
        back.setOnClickListener(view -> finish());
        refresh.setOnClickListener(view -> loadLatest());
        test.setOnClickListener(view -> sendTest());

        AppPreferences preferences = new AppPreferences(this);
        if (!UrlPolicy.isAllowedSecureUrl(preferences.discoveryUrl())
                || !preferences.deviceId().matches("[0-9a-f]{24}")
                || preferences.token().length() < 24) {
            status.setText(R.string.career_pairing_required);
            refresh.setEnabled(false);
            test.setEnabled(false);
            return;
        }
        client = new CareerBriefingClient(
                preferences.discoveryUrl(),
                preferences.deviceId(),
                preferences.token()
        );
        loadLatest();
    }

    private void loadLatest() {
        if (client == null) {
            return;
        }
        setBusy(true, getString(R.string.career_loading));
        client.latest((response, error) -> runOnUiThread(() -> {
            setBusy(false, "");
            if (!error.isBlank()) {
                status.setText(error);
                return;
            }
            render(response);
        }));
    }

    private void sendTest() {
        if (client == null) {
            return;
        }
        setBusy(true, getString(R.string.career_test_sending));
        client.sendTest((response, error) -> runOnUiThread(() -> {
            String resultMessage = error;
            if (error.isBlank()) {
                resultMessage = response.optBoolean("notification_sent")
                        ? getString(R.string.career_test_sent)
                        : response.optString(
                                "warning",
                                getString(R.string.career_test_not_sent)
                        );
            }
            setBusy(false, resultMessage);
            if (error.isBlank() && response != null) {
                if (!response.optBoolean("notification_sent")) {
                    Toast.makeText(
                            this,
                            resultMessage,
                            Toast.LENGTH_LONG
                    ).show();
                }
                render(response.optJSONObject("briefing"));
            }
        }));
    }

    private void render(JSONObject briefing) {
        items.removeAllViews();
        if (briefing == null) {
            status.setText(R.string.career_no_brief_yet);
            return;
        }
        status.setText(briefing.optString(
                "summary",
                getString(R.string.career_no_new_updates)
        ));
        JSONArray entries = briefing.optJSONArray("items");
        if (entries == null || entries.length() == 0) {
            return;
        }
        for (int index = 0; index < entries.length(); index++) {
            JSONObject entry = entries.optJSONObject(index);
            if (entry != null) {
                items.addView(itemView(entry));
            }
        }
    }

    private View itemView(JSONObject entry) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(16), dp(18), dp(16));
        card.setBackgroundResource(R.drawable.report_background);
        LinearLayout.LayoutParams cardLayout = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        cardLayout.setMargins(0, dp(12), 0, 0);
        card.setLayoutParams(cardLayout);

        TextView badge = new TextView(this);
        badge.setText(entry.optString("kind", "UPDATE")
                .toUpperCase(Locale.ROOT));
        badge.setTextColor(getColor(R.color.success));
        badge.setTextSize(12);
        badge.setTypeface(Typeface.DEFAULT_BOLD);
        card.addView(badge);

        TextView title = new TextView(this);
        title.setText(entry.optString("title", "Career update"));
        title.setTextColor(getColor(R.color.text_primary));
        title.setTextSize(17);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, dp(7), 0, 0);
        card.addView(title);

        TextView source = new TextView(this);
        String sourceName = entry.optString("source", "Source");
        String published = entry.optString("published_at", "");
        source.setText(published.isBlank()
                ? sourceName
                : sourceName + " • " + published);
        source.setTextColor(getColor(R.color.text_secondary));
        source.setTextSize(13);
        source.setPadding(0, dp(6), 0, 0);
        card.addView(source);

        String link = entry.optString("link", "");
        Button open = new Button(this);
        open.setText(R.string.career_open_source);
        open.setAllCaps(false);
        open.setEnabled(UrlPolicy.isAllowedSecureUrl(link));
        open.setOnClickListener(view -> startActivity(
                new Intent(Intent.ACTION_VIEW, Uri.parse(link))
        ));
        LinearLayout.LayoutParams buttonLayout = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(48)
        );
        buttonLayout.setMargins(0, dp(10), 0, 0);
        open.setLayoutParams(buttonLayout);
        card.addView(open);
        return card;
    }

    private void setBusy(boolean busy, String message) {
        refresh.setEnabled(!busy);
        test.setEnabled(!busy);
        if (!message.isBlank()) {
            status.setText(message);
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        if (client != null) {
            client.close();
        }
        super.onDestroy();
    }
}
