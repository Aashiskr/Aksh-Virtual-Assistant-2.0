package com.aksh.remote;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

public final class CareerBriefingMessagingService
        extends FirebaseMessagingService {
    static final String CHANNEL_ID = "career_updates";
    private static final int NOTIFICATION_ID = 1124;

    @Override
    public void onNewToken(String token) {
        CareerBriefingManager.sync(getApplicationContext(), (ok, message) -> {
            // A refreshed token is registered silently. MainActivity shows setup errors.
        });
    }

    @Override
    public void onMessageReceived(RemoteMessage message) {
        Map<String, String> data = message.getData();
        if (!"career_briefing".equals(data.get("type"))) {
            return;
        }
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        NotificationManager manager = getSystemService(
                NotificationManager.class
        );
        if (manager == null) {
            return;
        }
        createChannel(manager);

        Intent open = new Intent(this, CareerBriefingActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP
                | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String title = valueOr(
                data.get("title"),
                getString(R.string.career_notification_title)
        );
        String body = valueOr(
                data.get("body"),
                getString(R.string.career_notification_body)
        );
        Notification.Builder notification =
                new Notification.Builder(this, CHANNEL_ID)
                        .setSmallIcon(R.drawable.ic_career_notification)
                        .setColor(getColor(R.color.accent))
                        .setContentTitle(title)
                        .setContentText(body)
                        .setStyle(new Notification.BigTextStyle()
                                .bigText(body))
                        .setContentIntent(pendingIntent)
                        .setAutoCancel(true)
                        .setCategory(Notification.CATEGORY_RECOMMENDATION);
        manager.notify(NOTIFICATION_ID, notification.build());
    }

    static void createChannel(NotificationManager manager) {
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "Aksh career updates",
                NotificationManager.IMPORTANCE_HIGH
        );
        channel.setDescription(
                "Daily B.Tech opportunities and government exam alerts"
        );
        manager.createNotificationChannel(channel);
    }

    private static String valueOr(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
