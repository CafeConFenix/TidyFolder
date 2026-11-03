"""CustomTkinter user interface."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import customtkinter as ctk

from . import __version__
from .ai import AIError, ClaudeClient
from .classifier import Classifier
from .config import DEFAULT_MODEL, Settings
from .categories import folder_name
from .i18n import LANGUAGES, t
from .organizer import (
    Cancelled, PlanItem, build_plan, execute_plan, is_dangerous, journal_size, undo_last,
)

CHECKED, UNCHECKED = "☑", "☐"


def open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


class SettingsWindow(ctk.CTkToplevel):
    """Settings dialog: topic-detection mode, API key and model."""

    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        self.lang = app.lang
        self.title(t(self.lang, "settings_title"))
        self.geometry("520x470")
        self.resizable(False, False)
        self.transient(app)
        self.after(150, self._grab)
        self._test_result: list[str] = []

        s = app.settings
        pad = {"padx": 24, "sticky": "w"}
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=t(self.lang, "mode_label"), font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, pady=(20, 6), **pad)
        self.mode_labels = [t(self.lang, "mode_keywords"), t(self.lang, "mode_ai")]
        self.mode_btn = ctk.CTkSegmentedButton(self, values=self.mode_labels, command=self._on_mode)
        self.mode_btn.set(self.mode_labels[1 if s.mode == "ai" else 0])
        self.mode_btn.grid(row=1, column=0, padx=24, sticky="ew")

        ctk.CTkLabel(self, text=t(self.lang, "privacy"), wraplength=470, justify="left",
                     text_color=("gray35", "gray65")).grid(row=2, column=0, pady=(10, 14), **pad)

        ctk.CTkLabel(self, text=t(self.lang, "api_key")).grid(row=3, column=0, pady=(0, 4), **pad)
        self.key_entry = ctk.CTkEntry(self, show="•", width=470)
        self.key_entry.insert(0, s.api_key)
        self.key_entry.grid(row=4, column=0, padx=24, sticky="w")
        self.show_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text=t(self.lang, "show_key"), variable=self.show_var,
                        command=lambda: self.key_entry.configure(show="" if self.show_var.get() else "•")
                        ).grid(row=5, column=0, pady=(8, 10), **pad)

        ctk.CTkLabel(self, text=t(self.lang, "model")).grid(row=6, column=0, pady=(0, 4), **pad)
        self.model_entry = ctk.CTkEntry(self, width=470)
        self.model_entry.insert(0, s.model or DEFAULT_MODEL)
        self.model_entry.grid(row=7, column=0, padx=24, sticky="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=8, column=0, pady=(14, 0), **pad)
        self.test_btn = ctk.CTkButton(row, text=t(self.lang, "test_conn"), width=150,
                                      fg_color="transparent", border_width=1,
                                      text_color=("gray10", "gray90"), command=self._test)
        self.test_btn.grid(row=0, column=0)
        self.test_label = ctk.CTkLabel(row, text="", wraplength=290, justify="left")
        self.test_label.grid(row=0, column=1, padx=12)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=9, column=0, pady=(20, 16), padx=24, sticky="e")
        ctk.CTkButton(buttons, text=t(self.lang, "close"), width=100, fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=self.destroy).grid(row=0, column=0, padx=8)
        ctk.CTkButton(buttons, text=t(self.lang, "save"), width=100, command=self._save).grid(row=0, column=1)
        self._on_mode(self.mode_btn.get())

    def _grab(self) -> None:
        try:
            self.grab_set()
            self.focus()
        except tk.TclError:
            pass

    def _mode_key(self) -> str:
        return "ai" if self.mode_btn.get() == self.mode_labels[1] else "keywords"

    def _on_mode(self, _value: str) -> None:
        state = "normal" if self._mode_key() == "ai" else "disabled"
        for widget in (self.key_entry, self.model_entry, self.test_btn):
            widget.configure(state=state)

    def _test(self) -> None:
        client = ClaudeClient(self.key_entry.get(), self.model_entry.get() or DEFAULT_MODEL)
        self.test_label.configure(text=t(self.lang, "testing"))
        self.test_btn.configure(state="disabled")
        self._test_result.clear()

        def work() -> None:
            try:
                client.test()
                self._test_result.append(t(self.lang, "test_ok"))
            except AIError as exc:
                self._test_result.append(t(self.lang, "test_fail", e=str(exc)))
            except Exception as exc:
                self._test_result.append(t(self.lang, "test_fail", e=str(exc)))

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_test)

    def _poll_test(self) -> None:
        if not self.winfo_exists():
            return
        if self._test_result:
            self.test_label.configure(text=self._test_result[0])
            self.test_btn.configure(state="normal")
        else:
            self.after(200, self._poll_test)

    def _save(self) -> None:
        s = self.app.settings
        s.mode = self._mode_key()
        s.api_key = self.key_entry.get().strip()
        s.model = self.model_entry.get().strip() or DEFAULT_MODEL
        s.save()
        self.destroy()


class App(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.settings = Settings.load()
        self.lang = self.settings.language
        self.geometry("1020x780")
        self.minsize(900, 660)

        self.items: list[PlanItem] = []
        self.source_root: Path | None = None
        self.dest_root: Path | None = None
        self.busy = False
        self.cancel_event = threading.Event()
        self.queue: queue.Queue = queue.Queue()
        self._translated: list[tuple[object, str]] = []
        self._status: tuple[str, dict] = ("status_ready", {})
        self.action_key = self.settings.default_action if self.settings.default_action in ("move", "copy") else "move"

        self.source_var = tk.StringVar(value=self.settings.last_source)
        self.dest_var = tk.StringVar(value=self.settings.last_dest)
        self.same_var = tk.BooleanVar(value=True)
        self.sub_var = tk.BooleanVar(value=self.settings.recursive)
        self.empty_var = tk.BooleanVar(value=self.settings.remove_empty)

        self._build()
        self._style_tree()
        self._toggle_same()
        self.apply_language()
        self._update_buttons()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # ------------------------------------------------------------------ helpers
    def tr(self, key: str, **kw) -> str:
        return t(self.lang, key, **kw)

    def _reg(self, widget, key: str):
        self._translated.append((widget, key))
        return widget

    def set_status(self, key: str, **kw) -> None:
        self._status = (key, kw)
        self.status_label.configure(text=self.tr(key, **kw))

    # ---------------------------------------------------------------------- UI
    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        card = dict(corner_radius=14)

        # Header ---------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="🗂  TidyFolder", font=ctk.CTkFont(size=28, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        self._reg(ctk.CTkLabel(header, text_color=("gray35", "gray65")), "tagline").grid(
            row=1, column=0, sticky="w")
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, rowspan=2, sticky="e")
        self.lang_btn = ctk.CTkSegmentedButton(right, values=list(LANGUAGES.values()), command=self._on_language)
        self.lang_btn.set(LANGUAGES[self.lang])
        self.lang_btn.grid(row=0, column=0, padx=(0, 10))
        self._reg(ctk.CTkButton(right, width=110, fg_color="transparent", border_width=1,
                                text_color=("gray10", "gray90"), command=self._open_settings), "settings"
                  ).grid(row=0, column=1)

        # Folders card ---------------------------------------------------------
        folders = ctk.CTkFrame(self, **card)
        folders.grid(row=1, column=0, sticky="ew", padx=22, pady=(10, 6))
        folders.grid_columnconfigure(1, weight=1)
        self._reg(ctk.CTkLabel(folders, anchor="w"), "source_folder").grid(row=0, column=0, padx=(16, 10), pady=(14, 6), sticky="w")
        ctk.CTkEntry(folders, textvariable=self.source_var).grid(row=0, column=1, pady=(14, 6), sticky="ew")
        self._reg(ctk.CTkButton(folders, width=110, command=lambda: self._browse(self.source_var)), "browse"
                  ).grid(row=0, column=2, padx=16, pady=(14, 6))
        self._reg(ctk.CTkLabel(folders, anchor="w"), "dest_folder").grid(row=1, column=0, padx=(16, 10), pady=6, sticky="w")
        self.dest_entry = ctk.CTkEntry(folders, textvariable=self.dest_var)
        self.dest_entry.grid(row=1, column=1, pady=6, sticky="ew")
        self.dest_btn = self._reg(ctk.CTkButton(folders, width=110, command=lambda: self._browse(self.dest_var)), "browse")
        self.dest_btn.grid(row=1, column=2, padx=16, pady=6)
        self._reg(ctk.CTkCheckBox(folders, variable=self.same_var, command=self._toggle_same), "same_as_source"
                  ).grid(row=2, column=1, sticky="w", pady=(2, 14))
        self.source_var.trace_add("write", lambda *_: self._sync_dest())

        # Options card ---------------------------------------------------------
        options = ctk.CTkFrame(self, **card)
        options.grid(row=2, column=0, sticky="ew", padx=22, pady=6)
        options.grid_columnconfigure(5, weight=1)
        self._reg(ctk.CTkCheckBox(options, variable=self.sub_var), "include_sub").grid(row=0, column=0, padx=16, pady=14)
        self._reg(ctk.CTkCheckBox(options, variable=self.empty_var), "remove_empty").grid(row=0, column=1, padx=10, pady=14)
        self._reg(ctk.CTkLabel(options), "default_action").grid(row=0, column=2, padx=(16, 6))
        self.action_btn = ctk.CTkSegmentedButton(options, command=self._on_default_action)
        self.action_btn.grid(row=0, column=3, padx=(0, 10))
        self.analyze_btn = self._reg(ctk.CTkButton(options, width=170, height=36, command=self.on_analyze,
                                                   font=ctk.CTkFont(weight="bold")), "analyze")
        self.analyze_btn.grid(row=0, column=6, padx=16, pady=10)

        # Preview card ---------------------------------------------------------
        preview = ctk.CTkFrame(self, **card)
        preview.grid(row=3, column=0, sticky="nsew", padx=22, pady=6)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(preview, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        top.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(top, anchor="w", font=ctk.CTkFont(weight="bold"))
        self.status_label.grid(row=0, column=0, sticky="w")
        self.progress = ctk.CTkProgressBar(top, width=260)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=(12, 0))
        self._reg(ctk.CTkLabel(preview, anchor="w", text_color=("gray40", "gray60"), font=ctk.CTkFont(size=12)),
                  "hint_click").grid(row=1, column=0, sticky="w", padx=16)

        tree_frame = ctk.CTkFrame(preview, fg_color="transparent")
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("sel", "file", "folder", "action"), show="headings",
                                 selectmode="extended", style="Tidy.Treeview")
        self.tree.column("sel", width=50, anchor="center", stretch=False)
        self.tree.column("file", width=430, anchor="w")
        self.tree.column("folder", width=200, anchor="w", stretch=False)
        self.tree.column("action", width=120, anchor="center", stretch=False)
        scroll = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Button-1>", self._on_tree_click)

        tools = ctk.CTkFrame(preview, fg_color="transparent")
        tools.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        small = dict(height=28, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"))
        self.tool_buttons = []
        for col, (key, fn) in enumerate([
            ("all_move", lambda: self._set_actions("move", False)),
            ("all_copy", lambda: self._set_actions("copy", False)),
            ("sel_move", lambda: self._set_actions("move", True)),
            ("sel_copy", lambda: self._set_actions("copy", True)),
            ("select_all", lambda: self._set_include(True)),
            ("select_none", lambda: self._set_include(False)),
        ]):
            b = self._reg(ctk.CTkButton(tools, command=fn, **small), key)
            b.grid(row=0, column=col, padx=4)
            self.tool_buttons.append(b)

        # Bottom bar -----------------------------------------------------------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=22, pady=(6, 16))
        bottom.grid_columnconfigure(2, weight=1)
        self.undo_btn = self._reg(ctk.CTkButton(bottom, fg_color="transparent", border_width=1,
                                                text_color=("gray10", "gray90"), command=self.on_undo), "undo")
        self.undo_btn.grid(row=0, column=0, padx=(0, 8))
        self.open_btn = self._reg(ctk.CTkButton(bottom, fg_color="transparent", border_width=1,
                                                text_color=("gray10", "gray90"), command=self._open_dest), "open_dest")
        self.open_btn.grid(row=0, column=1)
        self.cancel_btn = self._reg(ctk.CTkButton(bottom, width=110, fg_color="#b03a3a", hover_color="#8c2d2d",
                                                  command=self._cancel), "cancel")
        self.cancel_btn.grid(row=0, column=3, padx=8)
        self.organize_btn = self._reg(ctk.CTkButton(bottom, width=200, height=40, font=ctk.CTkFont(size=15, weight="bold"),
                                                    command=self.on_organize), "organize")
        self.organize_btn.grid(row=0, column=4)

    def _style_tree(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        bg, fg = ("#2b2b2b", "#dce4ee") if dark else ("#ffffff", "#1a1a1a")
        head = "#3a3a3a" if dark else "#e4e4e4"
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Tidy.Treeview", background=bg, fieldbackground=bg, foreground=fg,
                        borderwidth=0, rowheight=28, font=("Segoe UI", 10))
        style.map("Tidy.Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "#ffffff")])
        style.configure("Tidy.Treeview.Heading", background=head, foreground=fg, relief="flat",
                        font=("Segoe UI", 10, "bold"))
        style.map("Tidy.Treeview.Heading", background=[("active", head)])

    # ---------------------------------------------------------------- language
    def _on_language(self, label: str) -> None:
        self.lang = next(code for code, name in LANGUAGES.items() if name == label)
        self.settings.language = self.lang
        self.settings.save()
        self.apply_language()

    def apply_language(self) -> None:
        self.title(f"TidyFolder {__version__}")
        for widget, key in self._translated:
            widget.configure(text=self.tr(key))
        for col, key in (("file", "col_file"), ("folder", "col_folder"), ("action", "col_action")):
            self.tree.heading(col, text=self.tr(key))
        self.action_btn.configure(values=[self.tr("move"), self.tr("copy")])
        self.action_btn.set(self.tr(self.action_key))
        for iid in self.tree.get_children():
            self._refresh_row(iid)
        key, kw = self._status
        self.status_label.configure(text=self.tr(key, **kw))

    # ----------------------------------------------------------------- folders
    def _browse(self, var: tk.StringVar) -> None:
        folder = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if folder:
            var.set(folder)

    def _sync_dest(self) -> None:
        if self.same_var.get():
            self.dest_var.set(self.source_var.get())

    def _toggle_same(self) -> None:
        state = "disabled" if self.same_var.get() else "normal"
        self.dest_entry.configure(state=state)
        self.dest_btn.configure(state=state)
        self._sync_dest()

    def _on_default_action(self, label: str) -> None:
        self.action_key = "move" if label == self.tr("move") else "copy"

    # -------------------------------------------------------------------- tree
    def _row_values(self, item: PlanItem) -> tuple[str, str, str, str]:
        base = self.source_root or item.src.parent
        try:
            rel = os.path.relpath(item.src, base)
        except ValueError:
            rel = str(item.src)
        icon = "➜ " if item.action == "move" else "⧉ "
        return (CHECKED if item.include else UNCHECKED, rel, folder_name(item.category, self.lang),
                icon + self.tr(item.action))

    def _refresh_row(self, iid: str) -> None:
        self.tree.item(iid, values=self._row_values(self.items[int(iid)]))

    def _on_tree_click(self, event) -> str | None:
        if self.busy or self.tree.identify_region(event.x, event.y) != "cell":
            return None
        iid, col = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
        if not iid:
            return None
        item = self.items[int(iid)]
        if col == "#1":
            item.include = not item.include
        elif col == "#4":
            item.action = "copy" if item.action == "move" else "move"
        else:
            return None
        self._refresh_row(iid)
        self._update_summary()
        return "break"

    def _set_actions(self, action: str, selected_only: bool) -> None:
        iids = self.tree.selection() if selected_only else self.tree.get_children()
        for iid in iids:
            self.items[int(iid)].action = action
            self._refresh_row(iid)

    def _set_include(self, value: bool) -> None:
        for iid in self.tree.get_children():
            self.items[int(iid)].include = value
            self._refresh_row(iid)
        self._update_summary()

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(self.items):
            self.tree.insert("", "end", iid=str(index), values=self._row_values(item))
        self._update_summary()

    def _update_summary(self) -> None:
        chosen = [i for i in self.items if i.include]
        self.set_status("status_summary", n=len(self.items), sel=len(chosen),
                        folders=len({i.category for i in chosen}))
        self._update_buttons()

    def _update_buttons(self) -> None:
        idle = "disabled" if self.busy else "normal"
        self.analyze_btn.configure(state=idle)
        self.organize_btn.configure(state="normal" if not self.busy and any(i.include for i in self.items) else "disabled")
        self.undo_btn.configure(state="normal" if not self.busy and journal_size() else "disabled")
        self.open_btn.configure(state="normal" if self.dest_var.get() else "disabled")
        self.cancel_btn.configure(state="normal" if self.busy else "disabled")
        for b in self.tool_buttons:
            b.configure(state=idle)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self._update_buttons()

    # ------------------------------------------------------------------ actions
    def _validate_folders(self) -> tuple[Path, Path] | None:
        source = Path(self.source_var.get().strip()).expanduser()
        if not source.is_dir():
            messagebox.showwarning("TidyFolder", self.tr("err_no_source"))
            return None
        if is_dangerous(source):
            messagebox.showwarning("TidyFolder", self.tr("err_dangerous", path=source))
            return None
        dest_text = self.dest_var.get().strip()
        if not dest_text:
            messagebox.showwarning("TidyFolder", self.tr("err_no_dest"))
            return None
        dest = Path(dest_text).expanduser()
        if is_dangerous(dest):
            messagebox.showwarning("TidyFolder", self.tr("err_dangerous", path=dest))
            return None
        return source, dest

    def on_analyze(self) -> None:
        folders = self._validate_folders()
        if not folders:
            return
        source, dest = folders
        mode, key = self.settings.mode, self.settings.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if mode == "ai" and not key:
            messagebox.showwarning("TidyFolder", self.tr("err_no_key"))
            return
        self.source_root, self.dest_root = source, dest
        self.items = []
        self.tree.delete(*self.tree.get_children())
        self.cancel_event = threading.Event()
        self.progress.set(0)
        self.set_status("status_scanning")
        self._set_busy(True)
        classifier = Classifier(mode, key, self.settings.model)
        recursive, action, cancel = self.sub_var.get(), self.action_key, self.cancel_event

        def work() -> None:
            try:
                items = build_plan(source, dest, classifier, recursive, action,
                                   progress=lambda d, n: self.queue.put(("analyze", d, n)), cancel=cancel)
                self.queue.put(("plan", items, classifier.ai_error))
            except Cancelled:
                self.queue.put(("cancelled",))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def on_organize(self) -> None:
        folders = self._validate_folders()
        if not folders or not self.source_root:
            return
        source, dest = folders
        chosen = [i for i in self.items if i.include]
        moves = sum(i.action == "move" for i in chosen)
        if not messagebox.askyesno(self.tr("confirm_title"),
                                   self.tr("confirm_body", moves=moves, copies=len(chosen) - moves, dest=dest)):
            return
        self.dest_root = dest
        self.cancel_event = threading.Event()
        self.progress.set(0)
        self._set_busy(True)
        items, lang, remove_empty, cancel = list(self.items), self.lang, self.empty_var.get(), self.cancel_event
        self._save_folder_settings()

        def work() -> None:
            try:
                result = execute_plan(items, dest, source, lang, remove_empty,
                                      progress=lambda d, n: self.queue.put(("run", d, n)), cancel=cancel)
                self.queue.put(("executed", result))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def on_undo(self) -> None:
        count = journal_size()
        if not count:
            messagebox.showinfo("TidyFolder", self.tr("undo_none"))
            return
        if not messagebox.askyesno(self.tr("confirm_title"), self.tr("undo_confirm", n=count)):
            return
        self.progress.set(0)
        self._set_busy(True)

        def work() -> None:
            try:
                self.queue.put(("undone", undo_last(progress=lambda d, n: self.queue.put(("run", d, n)))))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _cancel(self) -> None:
        self.cancel_event.set()

    def _open_dest(self) -> None:
        text = self.dest_var.get().strip()
        if text and Path(text).expanduser().is_dir():
            open_path(Path(text).expanduser())

    def _open_settings(self) -> None:
        SettingsWindow(self)

    # ------------------------------------------------------------- worker queue
    def _poll(self) -> None:
        try:
            while True:
                self._handle(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, msg: tuple) -> None:
        kind = msg[0]
        if kind in ("analyze", "run"):
            done, total = msg[1], msg[2]
            self.progress.set(done / total if total else 0)
            self.set_status("status_analyzing" if kind == "analyze" else "status_running", done=done, total=total)
        elif kind == "plan":
            self.items, ai_error = msg[1], msg[2]
            self._fill_tree()
            self._set_busy(False)
            if not self.items:
                self.set_status("status_ready")
                messagebox.showinfo("TidyFolder", self.tr("err_no_files"))
            elif ai_error:
                messagebox.showwarning("TidyFolder", self.tr("warn_ai_fallback", e=ai_error))
        elif kind == "executed":
            res = msg[1]
            self.items = []
            self.tree.delete(*self.tree.get_children())
            self.progress.set(1)
            self.set_status("status_cancelled" if res.cancelled else "status_done",
                            ok=res.ok, skipped=res.skipped, err=len(res.errors))
            self._set_busy(False)
            if res.errors:
                messagebox.showwarning("TidyFolder", self.tr("errors_title") + "\n\n" + "\n".join(res.errors[:8]))
        elif kind == "undone":
            res = msg[1]
            self.progress.set(1)
            self.set_status("status_undone", ok=res.ok, err=len(res.errors))
            self._set_busy(False)
            if res.errors:
                messagebox.showwarning("TidyFolder", self.tr("errors_title") + "\n\n" + "\n".join(res.errors[:8]))
        elif kind == "cancelled":
            self.progress.set(0)
            self.set_status("status_cancelled")
            self._set_busy(False)
        elif kind == "error":
            self.set_status("status_ready")
            self._set_busy(False)
            messagebox.showerror("TidyFolder", msg[1])

    # ------------------------------------------------------------------- misc
    def _save_folder_settings(self) -> None:
        s = self.settings
        s.last_source = self.source_var.get().strip()
        s.last_dest = self.dest_var.get().strip()
        s.recursive = self.sub_var.get()
        s.remove_empty = self.empty_var.get()
        s.default_action = self.action_key
        s.save()

    def _on_close(self) -> None:
        self._save_folder_settings()
        self.cancel_event.set()
        self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
