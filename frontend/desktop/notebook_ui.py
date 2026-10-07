from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from backend.notebook import NotebookTask, SessionTaskNotebook

from .capture_privacy import set_capture_excluded
from .theme import ACCENT, BORDER, MUTED, PANEL_BG, SURFACE, SURFACE_ALT, TEXT


class TaskNotebookUI:
    def __init__(self, root: tk.Tk, notebook: SessionTaskNotebook):
        self.root = root
        self.notebook = notebook
        self.window: tk.Toplevel | None = None
        self.tree: ttk.Treeview | None = None
        self.details: tk.Text | None = None
        self.workspace_text = tk.StringVar(value="Current workspace: scanning…")
        self._visible_tasks: dict[str, NotebookTask] = {}

    def attach_menu(self, menu: tk.Menu) -> None:
        menu.add_command(label="Session Task Notebook", command=self.show)

    def show(self) -> None:
        if self.window and self.window.winfo_exists():
            self.refresh()
            self.window.deiconify()
            self.window.lift()
            return
        self._build()
        self.refresh()

    def refresh(self) -> None:
        if not self.tree:
            return
        self.notebook.refresh_workspace()
        self.workspace_text.set(self.notebook.workspace.spoken_summary())
        self.tree.delete(*self.tree.get_children())
        tasks = self.notebook.snapshot()
        self._visible_tasks = {task.id: task for task in tasks}
        for task in reversed(tasks):
            self.tree.insert(
                "",
                "end",
                iid=task.id,
                values=(
                    task.updated_at.strftime("%H:%M:%S"),
                    task.title,
                    task.status.value.replace("_", " ").title(),
                    task.completed_by.title() if task.completed_by else "—",
                ),
            )
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self._show_selected()
        else:
            self._set_details(
                "No Aksh command tasks yet. Current open apps are shown above."
            )

    def _build(self) -> None:
        window = tk.Toplevel(self.root)
        self.window = window
        window.title("Aksh · Session Task Notebook")
        window.geometry("860x560")
        window.minsize(680, 440)
        window.configure(bg=PANEL_BG)
        window.attributes("-topmost", True)
        self.root.after(30, lambda: set_capture_excluded(window))

        header = tk.Frame(window, bg=PANEL_BG)
        header.pack(fill="x", padx=18, pady=(16, 10))
        tk.Label(
            header,
            text="Session Task Notebook",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 15),
        ).pack(side="left")
        tk.Button(
            header,
            text="Refresh",
            command=self.refresh,
            bg=SURFACE_ALT,
            fg=TEXT,
            activebackground="#dfe3de",
            activeforeground=TEXT,
            relief="flat",
            padx=14,
            pady=5,
        ).pack(side="right")
        tk.Label(
            window,
            text=(
                "Only this Aksh session · automatically erased when Aksh closes"
            ),
            bg=PANEL_BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=18, pady=(0, 10))
        tk.Label(
            window,
            textvariable=self.workspace_text,
            bg=SURFACE,
            fg=TEXT,
            justify="left",
            anchor="w",
            wraplength=810,
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=18, pady=(0, 10))

        style = ttk.Style(window)
        style.configure(
            "Aksh.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground=TEXT,
            rowheight=28,
            borderwidth=0,
        )
        style.configure(
            "Aksh.Treeview.Heading",
            background=SURFACE_ALT,
            foreground=TEXT,
            relief="flat",
        )
        style.map(
            "Aksh.Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#ffffff")],
        )

        body = tk.PanedWindow(
            window,
            orient="vertical",
            bg=PANEL_BG,
            sashwidth=5,
            relief="flat",
        )
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        table_frame = tk.Frame(body, bg=PANEL_BG)
        tree = ttk.Treeview(
            table_frame,
            columns=("time", "task", "status", "completed_by"),
            show="headings",
            style="Aksh.Treeview",
            selectmode="browse",
        )
        self.tree = tree
        tree.heading("time", text="Time")
        tree.heading("task", text="Task")
        tree.heading("status", text="Status")
        tree.heading("completed_by", text="Completed by")
        tree.column("time", width=85, minwidth=75, stretch=False)
        tree.column("task", width=475, minwidth=260)
        tree.column("status", width=145, minwidth=120, stretch=False)
        tree.column("completed_by", width=120, minwidth=105, stretch=False)
        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=tree.yview,
        )
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        tree.bind("<<TreeviewSelect>>", lambda event: self._show_selected())
        body.add(table_frame, height=290)

        details = tk.Text(
            body,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1,
            wrap="word",
            padx=12,
            pady=10,
            font=("Consolas", 9),
            state="disabled",
        )
        self.details = details
        body.add(details, height=180)

    def _show_selected(self) -> None:
        if not self.tree:
            return
        selected = self.tree.selection()
        task = self._visible_tasks.get(selected[0]) if selected else None
        if task is None:
            self._set_details("Select a task to see its user and Aksh events.")
            return
        lines = [
            f"Task: {task.title}",
            f"Requested by: {task.requested_by} · Source: {task.source}",
            f"Assigned to: {task.assigned_to} · Completed by: "
            f"{task.completed_by or '—'}",
            "",
        ]
        for event in task.events:
            time = event.created_at.strftime("%H:%M:%S")
            lines.append(
                f"[{time}] {event.actor.upper()} · "
                f"{event.kind.replace('_', ' ')}\n{event.text}"
            )
        self._set_details("\n\n".join(lines))

    def _set_details(self, value: str) -> None:
        if not self.details:
            return
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", value)
        self.details.configure(state="disabled")
