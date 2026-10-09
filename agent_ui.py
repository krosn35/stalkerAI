import json
import os
import queue
import re
import threading
import tkinter.font as tkfont
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# Linux: avoid DPI scaling surprises
ctk.deactivate_automatic_dpi_awareness()
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "StalkerAI"

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




# ------------------------------------------------- SMOOTH (ANTI-ALIASED) ----
class SmoothFrame(tk.Canvas):
    def __init__(self, master, radius=12, fill=CARD, border=None, bw=1,
                 bg=BG, size=None):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, width=40, height=30)
        self.radius = radius
        self.fill = fill
        self.border = border
        self.bw = bw
        self.fixed = size
        self.inset = int(min(radius, 20) * 0.3) + (bw if border else 0) + 1
        self._photo = None
        self._key = None

        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(self.inset, self.inset, window=self.body, anchor="nw")
        if size:
            self.configure(width=size[0], height=size[1])
            self.itemconfigure(self._win, width=size[0] - 2 * self.inset,
                               height=size[1] - 2 * self.inset)
            self.body.pack_propagate(False)
        else:
            self.body.bind("<Configure>", lambda e: self._sync())
        self.bind("<Configure>", lambda e: self._render(e.width, e.height))
        self.after_idle(self._sync)

    def _sync(self):
        if self.fixed or not self.winfo_exists():
            return
        self.configure(width=self.body.winfo_reqwidth() + 2 * self.inset,
                       height=self.body.winfo_reqheight() + 2 * self.inset)

    def _render(self, w, h):
        if w < 6 or h < 6:
            return
        key = (w, h, self.fill, self.border)
        if key == self._key:
            return
        self._key = key
        s = 4
        r = min(self.radius, w // 2, h // 2)
        img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            (0, 0, w * s - 1, h * s - 1), radius=r * s, fill=self.fill,
            outline=self.border, width=self.bw * s)
        self._photo = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        self.delete("bg")
        self.create_image(0, 0, anchor="nw", image=self._photo, tags="bg")
        self.tag_lower("bg")


class SmoothButton(SmoothFrame):
    def __init__(self, master, text, command, fill, hover, fg="white",
                 font=None, radius=12, border=None, bg=BG, size=None,
                 padx=10, pady=2):
        super().__init__(master, radius=radius, fill=fill, border=border, bg=bg, size=size)
        self.command = command
        self.base = fill
        self.hover = hover
        self.fg = fg
        self.enabled = True
        self.label = tk.Label(self.body, text=text, fg=fg, bg=fill, font=font, cursor="hand2")
        if size:
            self.label.pack(expand=True)
        else:
            self.label.pack(padx=padx, pady=pady)
        for w in (self, self.body, self.label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _paint(self, color):
        self.fill = color
        self.body.configure(bg=color)
        self.label.configure(bg=color)
        self._render(self.winfo_width(), self.winfo_height())

    def _on_enter(self, _e):
        if self.enabled:
            self._paint(self.hover)

    def _on_leave(self, _e):
        try:
            under = self.winfo_containing(*self.winfo_pointerxy())
        except Exception:
            under = None
        if under in (self, self.body, self.label):
            return
        self._paint(self.base)

    def _on_click(self, _e):
        if self.enabled and self.command:
            self.command()

    def restyle(self, text=None, fill=None, hover=None):
        if text is not None:
            self.label.configure(text=text)
        if hover is not None:
            self.hover = hover
        if fill is not None:
            self.base = fill
            self._paint(fill)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.label.configure(fg=self.fg if enabled else MUTED,
                             cursor="hand2" if enabled else "arrow")
        self._paint(self.base)


# ---------------------------------------------------------------- AGENT ----
def run_agent(user_text, emit, stop_event):
    try:
        user_text = user_text.strip()
        match = re.search(r"(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?)", user_text)

        if match:
            url = match.group(0)
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            emit("tool", f"apify crawl {url}")

            profiles_list = apify_scrape(url)

            if not stop_event.is_set():
                # Emit raw list object log to terminal or debugging
                print("Structured Profiles Object:", json.dumps(profiles_list, indent=2))

                # Emit Markdown table format to the UI
                table_output = format_profiles_to_markdown_table(profiles_list)
                emit("token", table_output)
        else:
            emit("error", "Please provide a valid URL or domain.")

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
        return max(280, min(820, width - 110))

    def _track(self, label, kind):
        self.wrap_labels.append((label, kind))

    def _next_row(self):
        r = self.row
        self.row += 1
        return r

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

        logo = SmoothFrame(bar, radius=11, fill=ACCENT, size=(36, 36))
        logo.grid(row=0, column=0)
        tk.Label(logo.body, text="S", font=self.F(17, "bold"), fg="white",
                 bg=ACCENT).pack(expand=True)

        title = ctk.CTkFrame(bar, fg_color="transparent")
        title.grid(row=0, column=1, sticky="w", padx=(12, 0))
        ctk.CTkLabel(title, text=APP_NAME, font=self.F(16, "bold"),
                     text_color=TEXT).pack(anchor="w")

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")

        pill = SmoothFrame(right, radius=16, fill=PANEL, border=BORDER)
        pill.pack(side="left", padx=(0, 10))
        self.status_dot = tk.Label(pill.body, text="●", font=self.F(10), fg=GREEN, bg=PANEL)
        self.status_dot.pack(side="left", padx=(4, 4), pady=2)
        self.status_lbl = tk.Label(pill.body, text="Ready", font=self.F(12), fg=MUTED, bg=PANEL)
        self.status_lbl.pack(side="left", padx=(0, 8), pady=2)

        self.new_chat_btn = SmoothButton(
            right, text="+  New chat", command=self._reset_chat, radius=17,
            fill=PANEL, hover=CARD_HOVER, border=BORDER, fg=TEXT,
            font=self.F(12, "bold"), padx=10, pady=2)
        self.new_chat_btn.pack(side="left")

    def _set_status(self, text, color):
        self.status_lbl.configure(text=text)
        self.status_dot.configure(fg=color)

    def _build_welcome(self):
        self.welcome = ctk.CTkFrame(self.center, fg_color="transparent")
        self.welcome.grid(row=0, column=0, sticky="nsew")
        self.welcome.grid_columnconfigure(0, weight=1)
        self.welcome.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(self.welcome, fg_color="transparent")
        inner.grid(row=0, column=0)

        badge = SmoothFrame(inner, radius=22, fill=ACCENT_SOFT, border=ACCENT, size=(68, 68))
        badge.pack(pady=(0, 20))
        tk.Label(badge.body, text="S", font=self.F(30, "bold"), fg=ACCENT,
                 bg=ACCENT_SOFT).pack(expand=True)

        ctk.CTkLabel(inner, text="Who are we investigating?",
                     font=self.F(28, "bold"), text_color=TEXT).pack()
        ctk.CTkLabel(inner, text="Enter a domain, company, username.",
                     font=self.F(14, "bold"), text_color=TEXT).pack()

    def _build_dock(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=2, column=0, sticky="ew")
        wrap.grid_columnconfigure(0, weight=1)

        self.dock_border = BORDER
        self.dock_photo = None
        self._dock_key = None
        self.dock = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0, height=60)
        self.dock.grid(row=0, column=0, sticky="ew")

        self.entry = ctk.CTkTextbox(
            self.dock, height=44, fg_color=CARD, bg_color=CARD, corner_radius=0,
            border_width=0, font=self.F(14), text_color=TEXT, wrap="word",
            activate_scrollbars=False)
        self.send_btn = SmoothButton(
            self.dock, text="↑", command=self._on_action, radius=12,
            fill=ACCENT, hover=ACCENT_HOVER, font=self.F(18, "bold"),
            bg=CARD, size=(40, 40))

        self.entry_win = self.dock.create_window(0, 0, window=self.entry, anchor="w")
        self.btn_win = self.dock.create_window(0, 0, window=self.send_btn, anchor="e")
        self.dock.bind("<Configure>", lambda e: self._layout_dock())

        ctk.CTkLabel(wrap, text="Enter to send    ·    Shift+Enter for a new line",
                     font=self.F(10), text_color=MUTED).grid(row=1, column=0, pady=(6, 0))

        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", lambda e: None)
        self.entry.bind("<KeyRelease>", self._resize_entry)
        self.entry.bind("<FocusIn>", lambda e: self._set_dock_border(ACCENT))
        self.entry.bind("<FocusOut>", lambda e: self._set_dock_border(BORDER))
        self.entry.focus_set()

    def _set_dock_border(self, color):
        self.dock_border = color
        self._layout_dock()

    def _layout_dock(self):
        w = self.dock.winfo_width()
        if w < 100:
            return
        entry_h = int(self.entry.cget("height"))
        h = max(60, entry_h + 16)
        self.dock.configure(height=h)
        self.dock.coords(self.entry_win, 18, h // 2)
        self.dock.itemconfigure(self.entry_win, width=w - 18 - 66, height=entry_h)
        self.dock.coords(self.btn_win, w - 12, h - 30)

        key = (w, h, self.dock_border)
        if key != self._dock_key:
            self._dock_key = key
            self._render_dock_bg(w, h)

    def _render_dock_bg(self, w, h):
        scale = 4
        img = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            (0, 0, w * scale - 1, h * scale - 1), radius=16 * scale,
            fill=CARD, outline=self.dock_border, width=scale)
        img = img.resize((w, h), Image.LANCZOS)
        self.dock_photo = ImageTk.PhotoImage(img)
        self.dock.delete("bg")
        self.dock.create_image(0, 0, anchor="nw", image=self.dock_photo, tags="bg")
        self.dock.tag_lower("bg")

    def _on_enter(self, _event):
        self.send()
        return "break"

    def _resize_entry(self, _event=None):
        lines = int(self.entry.index("end-1c").split(".")[0])
        self.entry.configure(height=min(140, 24 + lines * 20))
        self._layout_dock()

    def _on_action(self):
        if self.busy:
            self.stop()
        else:
            self.send()

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

    def _add_user(self, text):
        holder = ctk.CTkFrame(self.feed, fg_color="transparent")
        holder.grid(row=self._next_row(), column=0, sticky="e", padx=(0, 8), pady=(12, 4))
        bubble = SmoothFrame(holder, radius=18, fill=ACCENT_SOFT, border=ACCENT)
        bubble.pack()
        lbl = ctk.CTkLabel(bubble.body, text=text, font=self.F(13), text_color=TEXT,
                           justify="left", anchor="w", wraplength=self._wrap("user"))
        lbl.pack(padx=8, pady=4)
        self._track(lbl, "user")

    def _add_agent(self):
        row = ctk.CTkFrame(self.feed, fg_color="transparent")
        row.grid(row=self._next_row(), column=0, sticky="w", padx=(0, 8), pady=(8, 4))

        avatar = SmoothFrame(row, radius=10, fill=ACCENT, size=(30, 30))
        avatar.pack(side="left", anchor="n", padx=(0, 12))
        tk.Label(avatar.body, text="S", font=self.F(13, "bold"), fg="white",
                 bg=ACCENT).pack(expand=True)

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
        chip = SmoothFrame(holder, radius=12, fill=PANEL, border=BORDER)
        chip.pack()
        ctk.CTkLabel(chip.body, text="●", font=self.F(9), text_color=color).pack(
            side="left", padx=(4, 6), pady=2)
        ctk.CTkLabel(chip.body, text=name, font=self.F(10, "bold"),
                     text_color=color).pack(side="left")
        lbl = ctk.CTkLabel(chip.body, text=text, font=self.F(11, mono=(kind == "tool")),
                           text_color=MUTED, justify="left", anchor="w",
                           wraplength=self._wrap("chip"))
        lbl.pack(side="left", padx=(8, 6), pady=2)
        self._track(lbl, "chip")

    def _add_error(self, text):
        holder = ctk.CTkFrame(self.feed, fg_color="transparent")
        holder.grid(row=self._next_row(), column=0, sticky="w", padx=(42, 8), pady=6)
        card = SmoothFrame(holder, radius=14, fill="#2A1215", border=RED)
        card.pack()
        ctk.CTkLabel(card.body, text="Something went wrong", font=self.F(12, "bold"),
                     text_color=RED).pack(anchor="w", padx=6, pady=(4, 2))
        lbl = ctk.CTkLabel(card.body, text=text, font=self.F(11), text_color=MUTED,
                           justify="left", anchor="w", wraplength=self._wrap("agent"))
        lbl.pack(anchor="w", padx=6, pady=(0, 4))
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

        btn = tk.Label(self.agent_body, text="Copy", fg=MUTED, bg=BG,
                       font=self.F(11), cursor="hand2")
        btn.pack(anchor="w", pady=(2, 0))
        btn.bind("<Button-1>", lambda e: copy())
        btn.bind("<Enter>", lambda e: btn.configure(fg=TEXT))
        btn.bind("<Leave>", lambda e: btn.configure(fg=MUTED))

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
        self.typing_lbl.configure(text=f"Working    {frames[self.typing_step % 4]}")
        self.typing_step += 1
        self.typing_job = self.after(280, self._typing_tick)

    def _clear_typing(self):
        if self.typing_job:
            self.after_cancel(self.typing_job)
            self.typing_job = None
        if self.typing_row is not None:
            self.typing_row.destroy()
            self.typing_row = None

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
            self.send_btn.restyle(text="■", fill=RED, hover="#B91C1C")
            self.new_chat_btn.set_enabled(False)
            self._set_status("Working", AMBER)
        else:
            self.send_btn.restyle(text="↑", fill=ACCENT, hover=ACCENT_HOVER)
            self.new_chat_btn.set_enabled(True)
            self._set_status("Ready", GREEN)

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
                    self.agent_label = None
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