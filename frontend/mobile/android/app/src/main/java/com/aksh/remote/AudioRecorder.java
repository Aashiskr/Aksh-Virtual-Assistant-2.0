package com.aksh.remote;

import android.content.Context;
import android.media.MediaRecorder;
import android.os.Build;

import java.io.File;
import java.io.IOException;

final class AudioRecorder {
    private MediaRecorder recorder;
    private File output;

    File start(Context context) throws IOException {
        output = new File(
                context.getCacheDir(),
                "aksh-command-" + System.currentTimeMillis() + ".m4a"
        );
        recorder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                ? new MediaRecorder(context)
                : new MediaRecorder();
        recorder.setAudioSource(
                MediaRecorder.AudioSource.VOICE_RECOGNITION
        );
        recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
        recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
        recorder.setAudioChannels(1);
        recorder.setAudioSamplingRate(16000);
        recorder.setAudioEncodingBitRate(64000);
        recorder.setOutputFile(output.getAbsolutePath());
        recorder.prepare();
        recorder.start();
        return output;
    }

    File stop() {
        if (recorder == null) {
            return null;
        }
        try {
            recorder.stop();
        } finally {
            recorder.reset();
            recorder.release();
            recorder = null;
        }
        return output;
    }

    void cancel() {
        if (recorder == null) {
            return;
        }
        try {
            recorder.stop();
        } catch (RuntimeException ignored) {
        } finally {
            recorder.release();
            recorder = null;
            if (output != null) {
                output.delete();
            }
        }
    }

    boolean isRecording() {
        return recorder != null;
    }
}
