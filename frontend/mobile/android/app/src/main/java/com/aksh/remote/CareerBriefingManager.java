package com.aksh.remote;

import android.content.Context;

import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;

final class CareerBriefingManager {
    interface Listener {
        void onComplete(boolean ok, String message);
    }

    private CareerBriefingManager() {
    }

    static void sync(Context context, Listener listener) {
        AppPreferences preferences = new AppPreferences(context);
        if (!validPairing(preferences)) {
            listener.onComplete(false, "Relay pairing save karne ke baad updates enable honge.");
            return;
        }
        boolean enabled = preferences.careerBriefingEnabled();
        if (!enabled) {
            register(context, preferences, "", false, listener);
            return;
        }
        try {
            if (FirebaseApp.getApps(context).isEmpty()) {
                FirebaseApp.initializeApp(context);
            }
            if (FirebaseApp.getApps(context).isEmpty()) {
                listener.onComplete(
                        false,
                        "Firebase configuration missing hai. google-services.json add karein."
                );
                return;
            }
            FirebaseMessaging.getInstance().getToken()
                    .addOnCompleteListener(task -> {
                        if (!task.isSuccessful()
                                || task.getResult() == null
                                || task.getResult().isBlank()) {
                            listener.onComplete(
                                    false,
                                    "Phone push token available nahi hua."
                            );
                            return;
                        }
                        register(
                                context,
                                preferences,
                                task.getResult(),
                                true,
                                listener
                        );
                    });
        } catch (RuntimeException exception) {
            listener.onComplete(
                    false,
                    "Firebase setup incomplete hai: " + cleanError(exception)
            );
        }
    }

    private static void register(
            Context context,
            AppPreferences preferences,
            String fcmToken,
            boolean enabled,
            Listener listener
    ) {
        CareerBriefingClient client = new CareerBriefingClient(
                preferences.discoveryUrl(),
                preferences.deviceId(),
                preferences.token()
        );
        client.register(fcmToken, enabled, (response, error) -> {
            client.close();
            if (!error.isBlank()) {
                listener.onComplete(false, error);
                return;
            }
            listener.onComplete(
                    true,
                    enabled
                            ? "Daily 11 AM career updates active hain."
                            : "Daily career updates off hain."
            );
        });
    }

    private static boolean validPairing(AppPreferences preferences) {
        return UrlPolicy.isAllowedSecureUrl(preferences.discoveryUrl())
                && preferences.deviceId().matches("[0-9a-f]{24}")
                && preferences.token().length() >= 24;
    }

    private static String cleanError(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.isBlank()
                ? exception.getClass().getSimpleName()
                : message;
    }
}
