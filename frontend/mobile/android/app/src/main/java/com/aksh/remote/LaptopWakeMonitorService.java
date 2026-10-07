package com.aksh.remote;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.IBinder;
import android.util.Log;

import org.json.JSONObject;

public final class LaptopWakeMonitorService extends Service {
    private static final String TAG = "AkshWakeMonitor";
    private static final int MONITOR_NOTIFICATION_ID = 119;
    private static final int UNLOCK_NOTIFICATION_ID = 120;
    private static final String MONITOR_CHANNEL = "aksh_laptop_monitor";
    private static final String UNLOCK_CHANNEL = "aksh_laptop_wakeup";
    private static final String PREF_WAS_LOCKED = "monitor_was_locked";
    private static final String PREF_BOOT_ID = "monitor_last_boot_id";
    private static final long POLL_MS = 3000L;

    private volatile boolean stopping;
    private Thread worker;
    private UnlockApiClient client;

    @Override
    public void onCreate() {
        super.onCreate();
        createChannels();
        startForeground(
                MONITOR_NOTIFICATION_ID,
                monitorNotification()
        );
        client = new UnlockApiClient(this);
        worker = new Thread(
                this::monitor,
                "aksh-laptop-lock-monitor"
        );
        worker.setDaemon(true);
        worker.start();
    }

    @Override
    public int onStartCommand(
            Intent intent,
            int flags,
            int startId
    ) {
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void monitor() {
        SharedPreferences state = getSharedPreferences(
                "aksh_remote",
                MODE_PRIVATE
        );
        while (!stopping) {
            try {
                JSONObject health = client.healthSync();
                String computerState = health.optString(
                        "computer_state",
                        "unavailable"
                );
                boolean locked = "locked".equals(computerState);
                if (!"unavailable".equals(computerState)) {
                    boolean wasLocked = state.getBoolean(
                            PREF_WAS_LOCKED,
                            false
                    );
                    String bootId = health.optString("boot_id", "");
                    String previousBoot = state.getString(PREF_BOOT_ID, "");
                    boolean bootChanged = !bootId.equals(previousBoot);
                    Log.d(
                            TAG,
                            "health state=" + computerState
                                    + " wasLocked=" + wasLocked
                                    + " bootChanged=" + bootChanged
                    );
                    if (
                            locked
                                    && (!wasLocked
                                    || bootChanged)
                    ) {
                        postUnlockNotification();
                    }
                    state.edit()
                            .putBoolean(PREF_WAS_LOCKED, locked)
                            .putString(PREF_BOOT_ID, bootId)
                            .apply();
                }
            } catch (Exception exception) {
                // Offline is expected while the laptop is shut down.
                Log.w(TAG, "Monitor poll failed: " + exception);
                Log.w(TAG, Log.getStackTraceString(exception));
            }
            try {
                Thread.sleep(POLL_MS);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    private void createChannels() {
        NotificationManager manager =
                getSystemService(NotificationManager.class);
        if (manager == null) {
            Log.w(TAG, "Notification manager unavailable");
            return;
        }
        NotificationChannel monitor = new NotificationChannel(
                MONITOR_CHANNEL,
                getString(R.string.laptop_monitor_channel_name),
                NotificationManager.IMPORTANCE_LOW
        );
        monitor.setDescription(
                getString(R.string.laptop_monitor_message)
        );
        manager.createNotificationChannel(monitor);

        NotificationChannel unlock = new NotificationChannel(
                UNLOCK_CHANNEL,
                getString(R.string.laptop_wake_channel_name),
                NotificationManager.IMPORTANCE_HIGH
        );
        unlock.setDescription(
                getString(R.string.laptop_wake_channel_description)
        );
        unlock.enableVibration(true);
        unlock.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        manager.createNotificationChannel(unlock);
    }

    private Notification monitorNotification() {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(
                this,
                31,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT
                        | PendingIntent.FLAG_IMMUTABLE
        );
        return new Notification.Builder(this, MONITOR_CHANNEL)
                .setSmallIcon(R.drawable.ic_aksh)
                .setContentTitle(
                        getString(R.string.laptop_monitor_title)
                )
                .setContentText(
                        getString(R.string.laptop_monitor_message)
                )
                .setContentIntent(pending)
                .setOngoing(true)
                .setCategory(Notification.CATEGORY_SERVICE)
                .build();
    }

    private void postUnlockNotification() {
        NotificationManager manager =
                getSystemService(NotificationManager.class);
        if (manager == null) {
            return;
        }
        Intent openUnlock = new Intent(this, UnlockActivity.class)
                .addFlags(
                        Intent.FLAG_ACTIVITY_NEW_TASK
                                | Intent.FLAG_ACTIVITY_CLEAR_TOP
                );
        PendingIntent pending = PendingIntent.getActivity(
                this,
                32,
                openUnlock,
                PendingIntent.FLAG_UPDATE_CURRENT
                        | PendingIntent.FLAG_IMMUTABLE
        );
        Notification notification =
                new Notification.Builder(this, UNLOCK_CHANNEL)
                        .setSmallIcon(R.drawable.ic_aksh)
                        .setContentTitle(
                                getString(R.string.laptop_wake_title)
                        )
                        .setContentText(
                                getString(R.string.laptop_wake_message)
                        )
                        .setStyle(
                                new Notification.BigTextStyle().bigText(
                                        getString(
                                                R.string.laptop_wake_message
                                        )
                                )
                        )
                        .setContentIntent(pending)
                        .setAutoCancel(true)
                        .setCategory(Notification.CATEGORY_STATUS)
                        .setVisibility(Notification.VISIBILITY_PUBLIC)
                        .setDefaults(Notification.DEFAULT_ALL)
                        .addAction(
                                R.drawable.ic_fingerprint,
                                getString(R.string.laptop_wake_action),
                                pending
                        )
                        .build();
        try {
            manager.notify(UNLOCK_NOTIFICATION_ID, notification);
            Log.i(TAG, "Posted unlock notification");
        } catch (SecurityException exception) {
            // MainActivity requests notification access on Android 13+.
            Log.w(TAG, "Unable to post unlock notification", exception);
        }
    }

    @Override
    public void onDestroy() {
        stopping = true;
        if (worker != null) {
            worker.interrupt();
        }
        if (client != null) {
            client.close();
        }
        super.onDestroy();
    }
}
