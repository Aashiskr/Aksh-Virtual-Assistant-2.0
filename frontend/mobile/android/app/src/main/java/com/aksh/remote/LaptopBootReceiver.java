package com.aksh.remote;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class LaptopBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        LaptopWakeMonitor.sync(context);
    }
}
