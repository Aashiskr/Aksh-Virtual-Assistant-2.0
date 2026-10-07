from __future__ import annotations


def idle_status(
    settings,
    *,
    friends: bool,
    enrolled: bool,
    brain: bool,
    continuous_session_armed: bool = True,
):
    clap_enabled = settings.double_clap_enabled
    if not settings.wake_listener_enabled:
        if clap_enabled:
            return "sleeping", "Voice listening off · double clap ready"
        return "sleeping", "Microphone listening off"
    if friends:
        return "friends", "Friends Mode · permission guard active"
    if settings.voice_lock_enabled and not enrolled:
        return "setup", "Right-click → Enroll owner voice"
    if not brain:
        return "offline", "Groq key missing · local commands active"
    if settings.continuous_listening_enabled:
        if not continuous_session_armed:
            if clap_enabled:
                return "idle", "Say “Hey Aksh” or double-clap once"
            return "idle", "Say “Hey Aksh” once · then always listening"
        return "idle", "Always listening · say “mic off” to stop"
    manual_activation = (
        "double-clap or double-click" if clap_enabled else "double-click"
    )
    if not settings.voice_lock_enabled:
        return "idle", f"Voice open · say “Hey Aksh”, {manual_activation}"
    return "idle", f"Say “Hey Aksh”, {manual_activation}"
