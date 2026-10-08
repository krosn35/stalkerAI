"""StalkerAI - modern CustomTkinter UI for an AI agent.

Architecture:
- The UI lives in the main thread (CustomTkinter widgets).
- The agent runs in a worker thread and pushes events into a queue.Queue.
- _poll_events() drains the queue every 50 ms, so the UI never freezes.

Events the agent can emit: "token", "thought", "tool", "done", "error".
"""

import queue
import threading
import tkinter.font as tkfont
import customtkinter as ctk

# Linux: avoid DPI scaling surprises
ctk.deactivate_automatic_dpi_awareness()
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "StalkerAI"
MODEL = "gemini-3.8-flash"

# ---------------------------------------------------------------- THEME ----
BG = "#0B0C10"
PANEL = "#14151B"
CARD = "#1A1B23"
CARD_HOVER = "#22232F"
BORDER = "#2A2B36"
ACCENT = "#8B5CF6"
ACCENT_HOVER = "#7C3AED"
ACCENT_SOFT = "#251C45"
TEXT = "#E6E6EC"
MUTED = "#8E8F9A"
GREEN = "#34D399"
AMBER = "#F59E0B"
RED = "#EF4444"

# Starting points on the welcome screen: (title, subtitle, text put in the input)
QUICK_PROMPTS = []


# ---------------------------------------------------------------- AGENT ----
def run_agent(user_text, emit, stop_event):
    from google import genai
    try:
        client = genai.Client()
        stream = client.models.generate_content_stream(
            model=MODEL,
            contents=user_text,
        )
        for chunk in stream:
            if stop_event.is_set():
                break
            if chunk.text:
                emit("token", chunk.text)
        emit("done", "")
    except Exception as e:
        emit("error", str(e))


# ------------------------------------------------------------------ UI -----
class AgentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1100x720")
        self.minsize(820, 560)
        self.configure(fg_color=BG)

        self.family = self._pick_family(("Inter", "Noto Sans", "DejaVu Sans", "Segoe UI"))
        self.mono = self._pick_family(("JetBrains Mono", "DejaVu Sans Mono", "Consolas", "Courier New"))

        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.busy = False

        self.chat_started = False
        self.row = 0
        self.wrap_labels = []
        self.agent_label = None
        self.agent_body = None
        self.agent_text = ""
        self.turn_text = ""
        self.typing_row = None
        self.typing_lbl = None
        self.typing_job = None
        self.typing_step = 0
        self.resize_job = None

        self._build_ui()
        self.after(50, self._poll_events)

    # ------------------------------------------------------------ helpers --
    def _pick_family(self, options):
        available = set(tkfont.families(self))
        for name in options:
            if name in available:
                return name
        return None

    def F(self, size, weight="normal", mono=False):
        return ctk.CTkFont(family=self.mono if mono else self.family,
                           size=size, weight=weight)

    def _wrap(self, kind):
        width = self.center.winfo_width()
        if width < 50:
            width = 900
        if kind == "user":
            return max(260, min(680, int(width * 0.6)))
        if kind == "chip":
            return max(240, min(700, width - 200))
        return max(280, min(820, width - 110))  # agent / error

    def _track(self, label, kind):
        self.wrap_labels.append((label, kind))

    def _next_row(self):
        r = self.row
        self.row += 1
        return r

    # --------------------------------------------------------- main layout --
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.grid(row=0, column=0, sticky="nsew", padx=28, pady=(18, 16))
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        self._build_header(root)

        self.center = ctk.CTkFrame(root, fg_color="transparent")
        self.center.grid(row=1, column=0, sticky="nsew", pady=(14, 14))
        self.center.grid_columnconfigure(0, weight=1)
        self.center.grid_rowconfigure(0, weight=1)
        self.center.bind("<Configure>", self._on_resize)

        self._build_welcome()
        self._build_dock(root)

    def _build_header(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkFrame(bar, width=36, height=36, corner_radius=11, fg_color=ACCENT)
        logo.grid(row=0, column=0)
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="S", font=self.F(17, "bold"),
                     text_color="white").pack(expand=True)

        title = ctk.CTkFrame(bar, fg_color="transparent")
        title.grid(row=0, column=1, sticky="w", padx=(12, 0))
        ctk.CTkLabel(title, text=APP_NAME, font=self.F(16, "bold"),
                     text_color=TEXT).pack(anchor="w")

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")

        pill = ctk.CTkFrame(right, corner_radius=16, fg_color=PANEL,
                            border_width=1, border_color=BORDER)
        pill.pack(side="left", padx=(0, 10))
        self.status_dot = ctk.CTkLabel(pill, text="●", font=self.F(10), text_color=GREEN)
        self.status_dot.pack(side="left", padx=(12, 4), pady=6)
        self.status_lbl = ctk.CTkLabel(pill, text="Ready", font=self.F(12), text_color=MUTED)
        self.status_lbl.pack(side="left", padx=(0, 14))

        self.new_chat_btn = ctk.CTkButton(
            right, text="+  New chat", height=34, corner_radius=17,
            fg_color=PANEL, hover_color=CARD_HOVER, border_width=1,
            border_color=BORDER, text_color=TEXT, font=self.F(12, "bold"),
            command=self._reset_chat)
        self.new_chat_btn.pack(side="left")

    def _set_status(self, text, color):
        self.status_lbl.configure(text=text)
        self.status_dot.configure(text_color=color)

    # --------------------------------------------------------- welcome ------
    def _build_welcome(self):
        self.welcome = ctk.CTkFrame(self.center, fg_color="transparent")
        self.welcome.grid(row=0, column=0, sticky="nsew")
        self.welcome.grid_columnconfigure(0, weight=1)
        self.welcome.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(self.welcome, fg_color="transparent")
        inner.grid(row=0, column=0)

        badge = ctk.CTkFrame(inner, width=68, height=68, corner_radius=22,
                             fg_color=ACCENT_SOFT, border_width=1, border_color=ACCENT)
        badge.pack(pady=(0, 20))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="S", font=self.F(30, "bold"),
                     text_color=ACCENT).pack(expand=True)

        ctk.CTkLabel(inner, text="Who are we investigating?",
                     font=self.F(28, "bold"), text_color=TEXT).pack()
        ctk.CTkLabel(inner, text="Enter a domain, company, username.",
                     font=self.F(14, "bold"), text_color=TEXT).pack()


        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack()
        for i, (title, sub, prompt) in enumerate(QUICK_PROMPTS):
            self._quick_card(grid, title, sub, prompt).grid(
                row=i // 2, column=i % 2, padx=7, pady=7)

    def _quick_card(self, parent, title, sub, prompt):
        card = ctk.CTkFrame(parent, width=300, height=84, corner_radius=14,
                            fg_color=CARD, border_width=1, border_color=BORDER)
        card.pack_propagate(False)
        t = ctk.CTkLabel(card, text=title, font=self.F(13, "bold"),
                         text_color=TEXT, anchor="w")
        t.pack(anchor="w", padx=16, pady=(16, 2))
        s = ctk.CTkLabel(card, text=sub, font=self.F(11), text_color=MUTED,
                         anchor="w", justify="left", wraplength=268)
        s.pack(anchor="w", padx=16)

        def enter(_e):
            card.configure(fg_color=CARD_HOVER, border_color=ACCENT)

        def leave(_e):
            card.configure(fg_color=CARD, border_color=BORDER)

        for w in (card, t, s):
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
            w.bind("<Button-1>", lambda _e, p=prompt: self._use_prompt(p))
        return card

    def _use_prompt(self, prompt):
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", prompt)
        self._resize_entry()
        self.entry.focus_set()

    # --------------------------------------------------------- input dock ---
    def _build_dock(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=2, column=0, sticky="ew")
        wrap.grid_columnconfigure(0, weight=1)

        self.dock = ctk.CTkFrame(wrap, corner_radius=24, fg_color=CARD,
                                 border_width=1, border_color=BORDER)
        self.dock.grid(row=0, column=0, sticky="ew")
        self.dock.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkTextbox(
            self.dock, height=44, fg_color="transparent", border_width=0,
            font=self.F(14), text_color=TEXT, wrap="word",
            activate_scrollbars=False)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(18, 6), pady=8)

        self.send_btn = ctk.CTkButton(
            self.dock, text="↑", width=42, height=42, corner_radius=21,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=self.F(18, "bold"), command=self._on_action)
        self.send_btn.grid(row=0, column=1, padx=(0, 10), pady=8, sticky="s")

        ctk.CTkLabel(wrap, text="Enter to send   ·   Shift+Enter for a new line",
                     font=self.F(10), text_color=MUTED).grid(row=1, column=0, pady=(6, 0))

        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", lambda e: None)  # keep default: newline
        self.entry.bind("<KeyRelease>", self._resize_entry)
        self.entry.bind("<FocusIn>", lambda e: self.dock.configure(border_color=ACCENT))
        self.entry.bind("<FocusOut>", lambda e: self.dock.configure(border_color=BORDER))
        self.entry.focus_set()

    def _on_enter(self, _event):
        self.send()
        return "break"  # don't insert a newline

    def _resize_entry(self, _event=None):
        lines = int(self.entry.index("end-1c").split(".")[0])
        self.entry.configure(height=min(140, 24 + lines * 20))

    def _on_action(self):
        if self.busy:
            self.stop()
        else:
            self.send()

    # ------------------------------------------------------- chat feed ------
    def _show_chat(self):
        if self.chat_started:
            return
        self.welcome.destroy()
        self.feed = ctk.CTkScrollableFrame(
            self.center, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        self.feed.grid(row=0, column=0, sticky="nsew")
        self.feed.grid_columnconfigure(0, weight=1)
        self.chat_started = True
        self.row = 0
        self.wrap_labels = []

    def _reset_chat(self):
        if self.busy:
            return
        if self.chat_started:
            self._clear_typing()
            self.feed.destroy()
            self.chat_started = False
            self.agent_label = None
            self.agent_body = None
            self.wrap_labels = []
            self._build_welcome()
        self.entry.focus_set()

    def _on_resize(self, _event):
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(80, self._apply_wrap)

    def _apply_wrap(self):
        self.resize_job = None
        alive = []
        for label, kind in self.wrap_labels:
            if label.winfo_exists():
                label.configure(wraplength=self._wrap(kind))
                alive.append((label, kind))
        self.wrap_labels = alive

    def _at_bottom(self):
        if not self.chat_started:
            return True
        try:
            return self.feed._parent_canvas.yview()[1] >= 0.97
        except Exception:
            return True

    def _scroll_bottom(self):
        def go():
            try:
                self.feed._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass
        if self.chat_started:
            self.after(40, go)

    # ------------------------------------------------------ message blocks --
    def _add_user(self, text):
        holder = ctk.CTkFrame(self.feed, fg_color="transparent")
        holder.grid(row=self._next_row(), column=0, sticky="e", padx=(0, 8), pady=(12, 4))
        bubble = ctk.CTkFrame(holder, corner_radius=18, fg_color=ACCENT_SOFT,
                              border_width=1, border_color=ACCENT)
        bubble.pack()
        lbl = ctk.CTkLabel(bubble, text=text, font=self.F(13), text_color=TEXT,
                           justify="left", anchor="w", wraplength=self._wrap("user"))
        lbl.pack(padx=16, pady=10)
        self._track(lbl, "user")

    def _add_agent(self):
        row = ctk.CTkFrame(self.feed, fg_color="transparent")
        row.grid(row=self._next_row(), column=0, sticky="w", padx=(0, 8), pady=(8, 4))

        avatar = ctk.CTkFrame(row, width=30, height=30, corner_radius=10, fg_color=ACCENT)
        avatar.pack(side="left", anchor="n", padx=(0, 12))
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text="S", font=self.F(13, "bold"),
                     text_color="white").pack(expand=True)

        body = ctk.CTkFrame(row, fg_color="transparent")
        body.pack(side="left", anchor="n")
        lbl = ctk.CTkLabel(body, text="", font=self.F(13), text_color=TEXT,
                           justify="left", anchor="w", wraplength=self._wrap("agent"))
        lbl.pack(anchor="w", pady=(4, 0))
        self._track(lbl, "agent")

        self.agent_label = lbl
        self.agent_body = body
        self.agent_text = ""

    def _add_chip(self, kind, text):
        color = AMBER if kind == "tool" else MUTED
        name = "tool" if kind == "tool" else "thinking"

        holder = ctk.CTkFrame(self.feed, fg_color="transparent")
        holder.grid(row=self._next_row(), column=0, sticky="w", padx=(42, 8), pady=3)
        chip = ctk.CTkFrame(holder, corner_radius=10, fg_color=PANEL,
                            border_width=1, border_color=BORDER)
        chip.pack()
        ctk.CTkLabel(chip, text="●", font=self.F(9), text_color=color).pack(
            side="left", padx=(10, 6), pady=6)
        ctk.CTkLabel(chip, text=name, font=self.F(10, "bold"),
                     text_color=color).pack(side="left")
        lbl = ctk.CTkLabel(chip, text=text, font=self.F(11, mono=(kind == "tool")),
                           text_color=MUTED, justify="left", anchor="w",
                           wraplength=self._wrap("chip"))
        lbl.pack(side="left", padx=(8, 12), pady=6)
        self._track(lbl, "chip")

    def _add_error(self, text):
        holder = ctk.CTkFrame(self.feed, fg_color="transparent")
        holder.grid(row=self._next_row(), column=0, sticky="w", padx=(42, 8), pady=6)
        card = ctk.CTkFrame(holder, corner_radius=12, fg_color="#2A1215",
                            border_width=1, border_color=RED)
        card.pack()
        ctk.CTkLabel(card, text="Something went wrong", font=self.F(12, "bold"),
                     text_color=RED).pack(anchor="w", padx=14, pady=(10, 2))
        lbl = ctk.CTkLabel(card, text=text, font=self.F(11), text_color=MUTED,
                           justify="left", anchor="w", wraplength=self._wrap("agent"))
        lbl.pack(anchor="w", padx=14, pady=(0, 10))
        self._track(lbl, "agent")

    def _add_copy_button(self):
        if not self.agent_body or not self.turn_text.strip():
            return
        text = self.turn_text

        def copy():
            self.clipboard_clear()
            self.clipboard_append(text)
            btn.configure(text="Copied")
            self.after(1200, lambda: btn.winfo_exists() and btn.configure(text="Copy"))

        btn = ctk.CTkButton(self.agent_body, text="Copy", width=54, height=24,
                            corner_radius=8, fg_color="transparent",
                            hover_color=CARD_HOVER, text_color=MUTED,
                            font=self.F(11), command=copy)
        btn.pack(anchor="w", pady=(2, 0))

    # ----------------------------------------------------- typing indicator --
    def _show_typing(self):
        if self.typing_row is not None:
            return
        row = ctk.CTkFrame(self.feed, fg_color="transparent")
        row.grid(row=self._next_row(), column=0, sticky="w", padx=(42, 8), pady=(6, 4))
        self.typing_lbl = ctk.CTkLabel(row, text="", font=self.F(12), text_color=MUTED)
        self.typing_lbl.pack()
        self.typing_row = row
        self.typing_step = 0
        self._typing_tick()

    def _typing_tick(self):
        if self.typing_row is None:
            return
        frames = ("●  ○  ○", "○  ●  ○", "○  ○  ●", "○  ●  ○")
        self.typing_lbl.configure(text=f"Working   {frames[self.typing_step % 4]}")
        self.typing_step += 1
        self.typing_job = self.after(280, self._typing_tick)

    def _clear_typing(self):
        if self.typing_job:
            self.after_cancel(self.typing_job)
            self.typing_job = None
        if self.typing_row is not None:
            self.typing_row.destroy()
            self.typing_row = None

    # ------------------------------------------------------------ actions ---
    def send(self):
        text = self.entry.get("1.0", "end").strip()
        if not text or self.busy:
            return
        self.entry.delete("1.0", "end")
        self._resize_entry()

        self._show_chat()
        self._add_user(text)
        self.agent_label = None
        self.agent_body = None
        self.agent_text = ""
        self.turn_text = ""

        self.stop_event.clear()
        self._set_busy(True)
        self._show_typing()
        self._scroll_bottom()

        self.worker = threading.Thread(
            target=run_agent,
            args=(text, lambda t, x: self.events.put((t, x)), self.stop_event),
            daemon=True,
        )
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        self._set_status("Stopping...", AMBER)

    def _set_busy(self, busy):
        self.busy = busy
        if busy:
            self.send_btn.configure(text="■", fg_color=RED, hover_color="#B91C1C")
            self.new_chat_btn.configure(state="disabled")
            self._set_status("Working", AMBER)
        else:
            self.send_btn.configure(text="↑", fg_color=ACCENT, hover_color=ACCENT_HOVER)
            self.new_chat_btn.configure(state="normal")
            self._set_status("Ready", GREEN)

    # ------------------------------------------------------ event polling ---
    def _flush_tokens(self, tokens):
        chunk = "".join(tokens)
        if not chunk:
            return
        if self.agent_label is None:
            self._clear_typing()
            self._add_agent()
        self.agent_text += chunk
        self.turn_text += chunk
        self.agent_label.configure(text=self.agent_text)

    def _poll_events(self):
        follow = self._at_bottom()
        changed = False
        tokens = []
        try:
            while True:
                kind, text = self.events.get_nowait()
                changed = True
                if kind == "token":
                    tokens.append(text)
                    continue
                self._flush_tokens(tokens)
                tokens = []

                if kind in ("thought", "tool"):
                    self._clear_typing()
                    self._add_chip(kind, text)
                    self.agent_label = None  # next tokens start a new answer block
                    self._show_typing()
                elif kind == "error":
                    self._clear_typing()
                    self._add_error(text)
                    self._set_busy(False)
                elif kind == "done":
                    self._clear_typing()
                    self._add_copy_button()
                    self._set_busy(False)
        except queue.Empty:
            pass
        self._flush_tokens(tokens)

        if changed and follow:
            self._scroll_bottom()
        self.after(50, self._poll_events)


if __name__ == "__main__":
    AgentApp().mainloop()