package com.aksh.remote;

final class CommandStatusText {
    private CommandStatusText() {
    }

    static String forState(String state) {
        switch (state) {
            case "connected":
                return "Connected ✓";
            case "resolving":
                return "Finding your laptop…";
            case "uploading":
                return "Sending audio…";
            case "sending_text":
                return "Sending command...";
            case "queued":
                return "Command queued…";
            case "processing":
                return "Aksh is working…";
            case "completed":
                return "Completed ✓";
            default:
                return state;
        }
    }
}
