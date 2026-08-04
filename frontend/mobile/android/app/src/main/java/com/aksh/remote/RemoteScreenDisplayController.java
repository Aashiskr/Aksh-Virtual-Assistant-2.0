package com.aksh.remote;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;

final class RemoteScreenDisplayController {
    private final Activity activity;
    private boolean expanded;

    RemoteScreenDisplayController(Activity activity) {
        this.activity = activity;
    }

    void toggleFullscreenLandscape() {
        expanded = !expanded;
        activity.setRequestedOrientation(
                expanded
                        ? ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                        : ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
        );
        setSystemBarsHidden(expanded);
    }

    @SuppressWarnings("deprecation")
    private void setSystemBarsHidden(boolean hidden) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController controller = activity.getWindow().getInsetsController();
            if (controller == null) {
                return;
            }
            int bars = WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars();
            if (hidden) {
                controller.hide(bars);
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                );
            } else {
                controller.show(bars);
            }
            return;
        }
        activity.getWindow().getDecorView().setSystemUiVisibility(
                hidden
                        ? View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        : View.SYSTEM_UI_FLAG_VISIBLE
        );
    }
}
