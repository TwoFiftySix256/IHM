from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from .command_router import CommandRouter
from .scheduler import ReminderService
from .stt import SpeechToText
from .task_manager import TaskManager


class AssistantTkApp(tk.Tk):
    """Interface graphique professionnelle pour l'assistante vocale Yollande."""

    COLORS = {
        "bg": "#f4f6f8",
        "surface": "#ffffff",
        "surface_alt": "#eef3f0",
        "sidebar": "#17212b",
        "sidebar_soft": "#223142",
        "text": "#1f2933",
        "muted": "#6b7280",
        "line": "#d8dee4",
        "primary": "#0f766e",
        "primary_dark": "#115e59",
        "danger": "#b42318",
        "warning": "#b7791f",
        "success": "#15803d",
    }

    def __init__(
        self,
        router: CommandRouter,
        task_manager: TaskManager,
        reminder_service: ReminderService,
        stt: Optional[SpeechToText] = None,
        tts_controller: object | None = None,
    ):
        super().__init__()
        self.router = router
        self.task_manager = task_manager
        self.reminder_service = reminder_service
        self.stt = stt
        self.tts_controller = tts_controller
        self.voice_paused = tk.BooleanVar(value=False)
        self.continuous_listening = False
        self._continuous_thread: Optional[threading.Thread] = None

        self.title("Yollande - Assistant vocal")
        self.geometry("1120x680")
        self.minsize(980, 600)
        self.configure(bg=self.COLORS["bg"])
        self._configure_style()
        self._build_ui()
        self.refresh_tasks()
        self.reminder_service.start()

        if os.getenv("ASSISTANT_AUTO_LISTEN", "1").strip().lower() in {"1", "true", "yes", "on", "oui"}:
            self.after(700, self.toggle_continuous_listening)
        if os.getenv("ASSISTANT_START_MINIMIZED", "0").strip().lower() in {"1", "true", "yes", "on", "oui"}:
            self.after(1200, self.iconify)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        self.option_add("*Font", ("Segoe UI", 10))
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self.COLORS["bg"])
        style.configure("Surface.TFrame", background=self.COLORS["surface"])
        style.configure("Sidebar.TFrame", background=self.COLORS["sidebar"])

        style.configure(
            "Title.TLabel",
            background=self.COLORS["bg"],
            foreground=self.COLORS["text"],
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.COLORS["bg"],
            foreground=self.COLORS["muted"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabel",
            background=self.COLORS["surface"],
            foreground=self.COLORS["text"],
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=self.COLORS["surface"],
            foreground=self.COLORS["muted"],
        )
        style.configure(
            "SidebarTitle.TLabel",
            background=self.COLORS["sidebar"],
            foreground="#f8fafc",
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "SidebarText.TLabel",
            background=self.COLORS["sidebar"],
            foreground="#cbd5e1",
            font=("Segoe UI", 10),
        )

        style.configure(
            "Primary.TButton",
            background=self.COLORS["primary"],
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", self.COLORS["primary_dark"])])

        style.configure(
            "Secondary.TButton",
            background="#e7edf0",
            foreground=self.COLORS["text"],
            borderwidth=0,
            focusthickness=0,
            padding=(12, 8),
        )
        style.map("Secondary.TButton", background=[("active", "#d7e1e5")])

        style.configure(
            "Danger.TButton",
            background="#fee2e2",
            foreground=self.COLORS["danger"],
            borderwidth=0,
            focusthickness=0,
            padding=(12, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Danger.TButton", background=[("active", "#fecaca")])

        style.configure(
            "Voice.TCheckbutton",
            background=self.COLORS["sidebar"],
            foreground="#e2e8f0",
            focuscolor=self.COLORS["sidebar"],
        )
        style.map(
            "Voice.TCheckbutton",
            background=[("active", self.COLORS["sidebar"])],
            foreground=[("active", "#ffffff")],
        )

        style.configure(
            "Treeview",
            background=self.COLORS["surface"],
            foreground=self.COLORS["text"],
            fieldbackground=self.COLORS["surface"],
            rowheight=34,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#e9eef2",
            foreground="#334155",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", self.COLORS["primary"])])

        style.configure(
            "Command.TEntry",
            fieldbackground="#ffffff",
            bordercolor=self.COLORS["line"],
            lightcolor=self.COLORS["line"],
            darkcolor=self.COLORS["line"],
            padding=(10, 8),
        )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(self, bg=self.COLORS["sidebar"], width=278)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        main = ttk.Frame(self, style="App.TFrame", padding=(28, 24, 28, 22))
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        self._build_sidebar(sidebar)
        self._build_main(main)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=self.COLORS["sidebar"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(28, 16))
        header.grid_columnconfigure(0, weight=1)

        ttk.Label(header, text="Yollande", style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Assistant vocal personnel",
            style="SidebarText.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        status_card = tk.Frame(parent, bg=self.COLORS["sidebar_soft"], highlightthickness=0)
        status_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(8, 20))
        status_card.grid_columnconfigure(0, weight=1)
        tk.Label(
            status_card,
            text="Etat vocal",
            bg=self.COLORS["sidebar_soft"],
            fg="#94a3b8",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))
        self.voice_state_label = tk.Label(
            status_card,
            text="Pret",
            bg=self.COLORS["sidebar_soft"],
            fg="#ffffff",
            font=("Segoe UI", 15, "bold"),
        )
        self.voice_state_label.grid(row=1, column=0, sticky="w", padx=16)
        self.voice_detail_label = tk.Label(
            status_card,
            text="Appelez Yollande pour commencer.",
            bg=self.COLORS["sidebar_soft"],
            fg="#cbd5e1",
            wraplength=210,
            justify="left",
        )
        self.voice_detail_label.grid(row=2, column=0, sticky="w", padx=16, pady=(4, 16))

        controls = tk.Frame(parent, bg=self.COLORS["sidebar"])
        controls.grid(row=2, column=0, sticky="ew", padx=20)
        controls.grid_columnconfigure(0, weight=1)

        self.continuous_button = ttk.Button(
            controls,
            text="Demarrer l'ecoute",
            command=self.toggle_continuous_listening,
            style="Primary.TButton",
        )
        self.continuous_button.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(
            controls,
            text="Ecouter une fois",
            command=self.listen_once,
            style="Secondary.TButton",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Checkbutton(
            controls,
            text="Suspendre l'ecoute",
            variable=self.voice_paused,
            style="Voice.TCheckbutton",
            command=self._sync_voice_state,
        ).grid(row=2, column=0, sticky="w", pady=(2, 18))

        tk.Label(
            controls,
            text="Diagnostics",
            bg=self.COLORS["sidebar"],
            fg="#94a3b8",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=3, column=0, sticky="w", pady=(6, 8))

        ttk.Button(
            controls,
            text="Tester le micro",
            command=self.show_microphones,
            style="Secondary.TButton",
        ).grid(row=4, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(
            controls,
            text="Tester la voix",
            command=self.test_voice,
            style="Secondary.TButton",
        ).grid(row=5, column=0, sticky="ew")

        footer = tk.Frame(parent, bg=self.COLORS["sidebar"])
        footer.grid(row=3, column=0, sticky="sew", padx=24, pady=(24, 22))
        parent.grid_rowconfigure(3, weight=1)
        tk.Label(
            footer,
            text="Mode local : taches et rappels",
            bg=self.COLORS["sidebar"],
            fg="#94a3b8",
            font=("Segoe UI", 9),
        ).pack(anchor="w")

    def _build_main(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ttk.Label(header, text="Tableau de bord", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Pilotez les rappels, les taches et la conversation vocale depuis une interface claire.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.summary_frame = ttk.Frame(parent, style="App.TFrame")
        self.summary_frame.grid(row=1, column=0, sticky="ew", pady=(22, 18))
        for index in range(3):
            self.summary_frame.grid_columnconfigure(index, weight=1, uniform="summary")

        self.total_value = self._summary_card(self.summary_frame, 0, "Total", "0", "Taches suivies")
        self.pending_value = self._summary_card(self.summary_frame, 1, "En attente", "0", "A traiter")
        self.done_value = self._summary_card(self.summary_frame, 2, "Terminees", "0", "Cloturees")

        command_panel = tk.Frame(parent, bg=self.COLORS["surface"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        command_panel.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        command_panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            command_panel,
            text="Commande rapide",
            bg=self.COLORS["surface"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 4))

        self.command_entry = ttk.Entry(command_panel, style="Command.TEntry")
        self.command_entry.grid(row=1, column=0, sticky="ew", padx=(18, 10), pady=(6, 16), ipady=4)
        self.command_entry.bind("<Return>", lambda _: self.send_text())
        self.command_entry.insert(0, "Yollande, rappelle-moi de...")
        self.command_entry.bind("<FocusIn>", self._clear_placeholder)

        ttk.Button(
            command_panel,
            text="Envoyer",
            command=self.send_text,
            style="Primary.TButton",
        ).grid(row=1, column=1, sticky="e", padx=(0, 18), pady=(6, 16))

        table_panel = tk.Frame(parent, bg=self.COLORS["surface"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        table_panel.grid(row=3, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)

        table_header = tk.Frame(table_panel, bg=self.COLORS["surface"])
        table_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        table_header.grid_columnconfigure(0, weight=1)
        tk.Label(
            table_header,
            text="Planning des taches",
            bg=self.COLORS["surface"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")

        table_actions = ttk.Frame(table_header, style="Surface.TFrame")
        table_actions.grid(row=0, column=1, sticky="e")
        ttk.Button(table_actions, text="Actualiser", command=self.refresh_tasks, style="Secondary.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(table_actions, text="Terminer", command=self.mark_selected_done, style="Secondary.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(table_actions, text="Supprimer", command=self.delete_selected, style="Danger.TButton").pack(side=tk.LEFT)

        tree_wrap = ttk.Frame(table_panel, style="Surface.TFrame")
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 16))
        tree_wrap.grid_columnconfigure(0, weight=1)
        tree_wrap.grid_rowconfigure(0, weight=1)

        columns = ("heure", "tache", "statut")
        self.tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("heure", text="Date et heure")
        self.tree.heading("tache", text="Tache")
        self.tree.heading("statut", text="Statut")
        self.tree.column("heure", width=165, anchor="center", stretch=False)
        self.tree.column("tache", width=520, anchor="w")
        self.tree.column("statut", width=130, anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f8fafc")
        self.tree.tag_configure("done", foreground=self.COLORS["muted"])
        self.tree.tag_configure("pending", foreground=self.COLORS["text"])

        self.status_bar = tk.Label(
            parent,
            text="Service de rappel actif. Appelez Yollande pour lui parler.",
            bg=self.COLORS["surface_alt"],
            fg="#334155",
            anchor="w",
            padx=14,
            pady=9,
            font=("Segoe UI", 9),
        )
        self.status_bar.grid(row=4, column=0, sticky="ew", pady=(14, 0))

    def _summary_card(self, parent: ttk.Frame, column: int, title: str, value: str, detail: str) -> tk.Label:
        card = tk.Frame(parent, bg=self.COLORS["surface"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))
        tk.Label(
            card,
            text=title,
            bg=self.COLORS["surface"],
            fg=self.COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=16, pady=(13, 0))
        value_label = tk.Label(
            card,
            text=value,
            bg=self.COLORS["surface"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 24, "bold"),
        )
        value_label.pack(anchor="w", padx=16, pady=(0, 0))
        tk.Label(
            card,
            text=detail,
            bg=self.COLORS["surface"],
            fg=self.COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(0, 13))
        return value_label

    def _clear_placeholder(self, _: tk.Event) -> None:
        if self.command_entry.get() == "Yollande, rappelle-moi de...":
            self.command_entry.delete(0, tk.END)

    def _set_status(self, message: str, voice_state: str | None = None, detail: str | None = None) -> None:
        self.status_bar.config(text=message)
        if voice_state is not None:
            self.voice_state_label.config(text=voice_state)
        if detail is not None:
            self.voice_detail_label.config(text=detail)

    def _sync_voice_state(self) -> None:
        if self.voice_paused.get():
            self._set_status("Ecoute vocale suspendue.", "Suspendue", "Decochez l'option pour reprendre l'ecoute.")
        elif self.continuous_listening:
            self._set_status("Ecoute continue active.", "En ecoute", "Yollande attend votre voix.")
        else:
            self._set_status("Service de rappel actif.", "Pret", "Appelez Yollande pour commencer.")

    def send_text(self) -> None:
        text = self.command_entry.get().strip()
        if not text or text == "Yollande, rappelle-moi de...":
            return
        self.command_entry.delete(0, tk.END)
        response = self.router.handle_text(text)
        self._set_status(response)
        self.refresh_tasks()

    def listen_once(self) -> None:
        if self.voice_paused.get():
            self._set_status("Ecoute vocale suspendue.", "Suspendue", "La capture audio est en pause.")
            return
        if self.stt is None:
            messagebox.showwarning("Microphone", "Le module SpeechRecognition/PyAudio n'est pas disponible.")
            return
        self._set_status("J'ecoute... parlez maintenant.", "Ecoute ponctuelle", "Une phrase sera capturee.")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def toggle_continuous_listening(self) -> None:
        if self.stt is None:
            messagebox.showwarning("Microphone", "Le module SpeechRecognition/PyAudio n'est pas disponible.")
            return
        if self.continuous_listening:
            self.continuous_listening = False
            self.continuous_button.config(text="Demarrer l'ecoute")
            self._set_status("Ecoute continue arretee.", "Pret", "Appelez Yollande quand vous relancez l'ecoute.")
            return
        self.continuous_listening = True
        self.continuous_button.config(text="Arreter l'ecoute")
        self._set_status("Ecoute continue active.", "En ecoute", "Parlez apres le nom Yollande.")
        self._continuous_thread = threading.Thread(target=self._continuous_worker, daemon=True)
        self._continuous_thread.start()

    def _continuous_worker(self) -> None:
        while self.continuous_listening:
            if self.voice_paused.get():
                time.sleep(0.5)
                continue
            result = self.stt.listen_once() if self.stt is not None else None
            if not self.continuous_listening:
                break
            if result is None:
                continue
            if result.ok and result.text:
                self._interrupt_speech()
                self.after(0, lambda text=result.text: self._use_voice_text(text))
                time.sleep(0.45)
            else:
                self.after(0, lambda err=result.error: self._set_status(err, "En ecoute", "Je reste disponible."))
                time.sleep(0.3)

    def _listen_worker(self) -> None:
        result = self.stt.listen_once() if self.stt is not None else None
        if result is None:
            return
        if not result.ok:
            self.after(0, lambda: self._set_status(result.error, "Pret", "Reessayez quand vous voulez."))
            return
        self._interrupt_speech()
        self.after(0, lambda: self._use_voice_text(result.text))

    def _interrupt_speech(self) -> None:
        interrupt = getattr(self.tts_controller, "interrupt", None)
        if callable(interrupt):
            interrupt()

    def _use_voice_text(self, text: str) -> None:
        self.command_entry.delete(0, tk.END)
        self.command_entry.insert(0, text)
        self._set_status(f"J'ai entendu : {text}", "Traitement", "Je prepare la reponse.")
        self.send_text()

    def show_microphones(self) -> None:
        if self.stt is None:
            messagebox.showwarning("Microphone", "SpeechRecognition/PyAudio n'est pas disponible.")
            return
        try:
            microphones = self.stt.list_microphones()
        except Exception as exc:
            messagebox.showerror("Microphone", str(exc))
            return
        if not microphones:
            messagebox.showwarning("Microphone", "Aucun microphone detecte.")
            return
        message = "Microphones detectes :\n\n" + "\n".join(f"{i} - {name}" for i, name in enumerate(microphones))
        messagebox.showinfo("Microphones", message)

    def test_voice(self) -> None:
        speak = getattr(self.tts_controller, "say", None)
        if callable(speak):
            threading.Thread(
                target=lambda: speak("Oui, Ingenieur Hermes, je vous entends. La voix de Yollande fonctionne."),
                daemon=True,
            ).start()
            self._set_status("Test voix lance.", "Test voix", "Vous devriez entendre Yollande.")
            return
        messagebox.showwarning("Voix", "Le moteur vocal n'est pas disponible.")

    def refresh_tasks(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        tasks = self.task_manager.list_tasks()
        done_count = 0
        pending_count = 0

        for index, task in enumerate(tasks):
            status = str(task.status)
            is_done = "terminee" in status.lower() or "termin" in status.lower()
            done_count += 1 if is_done else 0
            pending_count += 0 if is_done else 1
            tags = ["even" if index % 2 == 0 else "odd", "done" if is_done else "pending"]
            self.tree.insert(
                "",
                tk.END,
                iid=task.task_id,
                values=(task.due_at.strftime("%d/%m/%Y %H:%M"), task.title, task.status),
                tags=tags,
            )

        self.total_value.config(text=str(len(tasks)))
        self.pending_value.config(text=str(pending_count))
        self.done_value.config(text=str(done_count))

    def _selected_task_id(self) -> Optional[str]:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def mark_selected_done(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            messagebox.showinfo("Selection", "Choisissez une tache.")
            return
        task = self.task_manager.mark_done(task_id)
        self._set_status(f"Tache terminee : {task.title}")
        self.refresh_tasks()

    def delete_selected(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            messagebox.showinfo("Selection", "Choisissez une tache.")
            return
        if not messagebox.askyesno("Confirmation", "Supprimer cette tache ?"):
            return
        task = self.task_manager.delete_task(task_id)
        self._set_status(f"Tache supprimee : {task.title}")
        self.refresh_tasks()

    def _on_close(self) -> None:
        self.continuous_listening = False
        self.reminder_service.stop()
        self.destroy()
