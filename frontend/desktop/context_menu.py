from __future__ import annotations

import tkinter as tk

from .theme import PANEL_BG, SURFACE_ALT, TEXT


def build_context_menu(app, pet_size_step: int):
    """Build the compact navigation menu; settings live in the slider panel."""

    context = tk.Menu(
        app.root,
        tearoff=0,
        bg=PANEL_BG,
        fg=TEXT,
        activebackground=SURFACE_ALT,
        activeforeground=TEXT,
        bd=1,
        relief="solid",
    )
    context.add_command(label="Talk now", command=lambda: app._activate("menu"))
    context.add_command(label="Type a command", command=app.show_panel)
    context.add_command(
        label="Settings · Voice & listening",
        command=app.show_settings,
    )
    context.add_command(
        label="Open Task Notebook PDF",
        command=app._open_notebook_pdf,
    )
    app.notebook_ui.attach_menu(context)
    app.meeting_ui.attach_menu(context)
    app.profile_ui.attach_menu(context)
    app.remote_ui.attach_menu(context)
    context.add_separator()
    if app.settings.voice_lock_enabled:
        context.add_command(
            label="Enroll owner voice",
            command=app._confirm_enrollment,
        )
    else:
        context.add_command(label="Voice lock: Off", state="disabled")

    size_menu = tk.Menu(
        context,
        tearoff=0,
        bg=PANEL_BG,
        fg=TEXT,
        activebackground=SURFACE_ALT,
        activeforeground=TEXT,
    )
    size_menu.add_command(
        label="−  Decrease",
        command=lambda: app._adjust_pet_size(-pet_size_step),
    )
    size_menu.add_command(
        label="+  Increase",
        command=lambda: app._adjust_pet_size(pet_size_step),
    )
    context.add_cascade(label="Pet size", menu=size_menu)

    wake_variable = tk.BooleanVar(value=app.settings.wake_listener_enabled)
    context.add_command(
        label=app._microphone_menu_label(app.settings.wake_listener_enabled),
        command=app.show_settings,
    )
    microphone_menu_index = context.index("end")
    double_clap_variable = tk.BooleanVar(value=app.settings.double_clap_enabled)
    continuous_variable = tk.BooleanVar(
        value=app.settings.continuous_listening_enabled
    )
    context.add_separator()
    context.add_command(label="Exit Aksh", command=app.close)
    return (
        context,
        microphone_menu_index,
        wake_variable,
        double_clap_variable,
        continuous_variable,
    )
