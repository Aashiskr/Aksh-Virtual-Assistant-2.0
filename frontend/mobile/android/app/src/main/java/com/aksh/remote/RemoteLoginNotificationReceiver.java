package com.aksh.remote;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class RemoteLoginNotificationReceiver
        extends BroadcastReceiver {
    static final String ACTION_OPEN_UNLOCK =
            "com.aksh.remote.ACTION_OPEN_PHONE_UNLOCK";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (ACTION_OPEN_UNLOCK.equals(intent.getAction())) {
            SecureRemoteLoginLauncher.openUnlock(context);
        }
    }
}
