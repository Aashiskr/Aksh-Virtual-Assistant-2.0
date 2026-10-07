package com.aksh.remote;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;

final class SecureRemoteLoginLauncher {
    private final Activity activity;

    SecureRemoteLoginLauncher(Activity activity) {
        this.activity = activity;
    }

    void requestOpen() {
        openUnlock(activity);
    }

    void close() {
        // Kept for MainActivity lifecycle symmetry.
    }

    static void openUnlock(Context context) {
        Intent intent = new Intent(context, UnlockActivity.class)
                .addFlags(
                        Intent.FLAG_ACTIVITY_NEW_TASK
                                | Intent.FLAG_ACTIVITY_CLEAR_TOP
                );
        context.startActivity(intent);
    }
}
