from __future__ import annotations


def idle_status(settings, *, friends: bool, enrolled: bool, brain: bool):
    if not settings.wake_listener_enabled:
        return "sleeping", "Microphone listening off"
    if friends:
        return "friends", "Friends Mode · permission guard active"
    if settings.voice_lock_enabled and not enrolled:
        return "setup", "Right-click → Enroll owner voice"
    if not brain:
        return "offline", "Groq key missing · local commands active"
    if settings.continuous_listening_enabled:
        return "idle", "Always listening · say “mic off” to stop"
    if not settings.voice_lock_enabled:
        return "idle", "Voice open · say “Hey Aksh” or double-click"
    return "idle", "Say “Hey Aksh” or double-click"
