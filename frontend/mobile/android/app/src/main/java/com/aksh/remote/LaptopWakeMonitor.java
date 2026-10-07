package com.aksh.remote;

import android.content.Context;
import android.content.Intent;
import android.os.Build;

final class LaptopWakeMonitor {
    private LaptopWakeMonitor() {
    }

    static void sync(Context context) {
        AppPreferences preferences = new AppPreferences(context);
        Intent service = new Intent(
                context,
                LaptopWakeMonitorService.class
        );
        if (!canMonitor(preferences)) {
            context.stopService(service);
            return;
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(service);
            } else {
                context.startService(service);
            }
        } catch (RuntimeException ignored) {
            // Android may defer boot-started services until the phone is unlocked.
        }
    }

    private static boolean canMonitor(AppPreferences preferences) {
        String discovery = preferences.discoveryUrl();
        String server = preferences.serverUrl();
        String token = preferences.token();
        String device = preferences.deviceId();
        return !token.isBlank()
                && (
                        UrlPolicy.isAllowedSecureUrl(server)
                                || (
                                !discovery.isBlank()
                                        && !device.isBlank()
                        )
                );
    }
}
