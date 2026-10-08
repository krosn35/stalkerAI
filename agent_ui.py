"""Modern CustomTkinter AI Agent UI.

Architecture:
- UI runs in the main thread with CustomTkinter components.

- Agent logic streams in a background worker thread.

- Queue polling updates UI dynamically without freezing the event loop.

- Opaque backgrounds configured for Linux compositors (Hyprland / Wayland).

"""

import queue
import threading
import customtkinter as ctk

# Color Palette inspired by modern AI workspaces
BG_DARK = "#0D0E12"       # Main workspace background
CARD_BG = "#1A1B23"       # Card / Agent response background
BORDER_PURPLE = "#8B5CF6" # Accent highlight
TEXT_MUTED = "#8E8F9A"    # Subtitles and muted labels

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------- AGENT ----
def run_agent(user_text, emit, stop_event):
    from google import genai
    try:
        client = genai.Client()
        stream = client.models.generate_content_stream(
            model="gemini-3.8-flash",
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
        self.title("StalkerAI")
        self.geometry("1100x700")
        self.minsize(850, 550)

        self.configure(fg_color=BG_DARK)

        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.current_agent_label = None
        self.is_chat_started = False

        self._build_widgets()
        self.after(50, self._poll_events)

    def _build_widgets(self):
        # Master Layout Grid (Single Column)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- MAIN WORKSPACE ----------------
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=30, pady=20)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # ---------------- TOP HEADER BAR ----------------
        self.top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent", height=40)
        self.top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        self.logo_lbl = ctk.CTkLabel(
            self.top_bar, text="🤖 StalkerAI", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_lbl.pack(side="left")

        # New Chat Pill Button moved to top bar
        self.new_chat_btn = ctk.CTkButton(
            self.top_bar,
            text="+ New Chat",
            height=34,
            corner_radius=17,
            fg_color="#272832",
            hover_color="#333444",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._reset_to_welcome
        )
        self.new_chat_btn.pack(side="right")

        # Center Container (Holds Welcome Screen or Scroll Feed)
        self.center_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.center_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        self.center_frame.grid_columnconfigure(0, weight=1)
        self.center_frame.grid_rowconfigure(0, weight=1)

        self._build_welcome_screen()
        self._build_floating_input_dock()

    def _build_welcome_screen(self):
        """Creates the centered landing screen with prompt cards."""
        self.welcome_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        self.welcome_frame.grid(row=0, column=0, sticky="nsew")
        self.welcome_frame.grid_columnconfigure(0, weight=1)

        header_container = ctk.CTkFrame(self.welcome_frame, fg_color="transparent")
        header_container.pack(expand=True)

        ctk.CTkLabel(header_container, text="StalkerAI", font=ctk.CTkFont(size=64), text_color=TEXT_MUTED).pack()
        ctk.CTkLabel(header_container, text="How Can I Assist You?", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(5, 30))

        # Quick Action Prompt Cards Row
        cards_row = ctk.CTkFrame(header_container, fg_color="transparent")
        cards_row.pack()

    def _create_quick_card(self, parent, title, subtitle):
        card = ctk.CTkFrame(parent, width=220, height=90, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color="#2A2B36")
        card.pack(side="left", padx=8)
        card.pack_propagate(False)

        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), wraplength=200, justify="left")
        lbl_title.pack(anchor="w", padx=12, pady=(12, 2))

        lbl_sub = ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=10), text_color=TEXT_MUTED, wraplength=200, justify="left")
        lbl_sub.pack(anchor="w", padx=12)

        for widget in (card, lbl_title, lbl_sub):
            widget.bind("<Button-1>", lambda e, t=title: self._quick_prompt_click(t))

    def _quick_prompt_click(self, prompt_text):
        self.entry.delete(0, "end")
        self.entry.insert(0, prompt_text)
        self.send()

    def _build_floating_input_dock(self):
        """Creates the floating input dock with action buttons."""
        self.input_dock = ctk.CTkFrame(
            self.main_container,
            height=60,
            corner_radius=20,
            fg_color=CARD_BG,
            border_width=1,
            border_color=BORDER_PURPLE
        )
        self.input_dock.grid(row=2, column=0, sticky="ew")
        self.input_dock.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self.input_dock,
            placeholder_text="Assign a task to the agent...",
            fg_color="transparent",
            border_width=0,
            font=ctk.CTkFont(size=14),
            height=50
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(15, 10), pady=5)
        self.entry.bind("<Return>", lambda e: self.send())

        dock_actions = ctk.CTkFrame(self.input_dock, fg_color="transparent")
        dock_actions.grid(row=0, column=1, padx=(0, 10))

        self.send_btn = ctk.CTkButton(
            dock_actions,
            text="Send",
            width=70,
            height=38,
            corner_radius=12,
            fg_color=BORDER_PURPLE,
            hover_color="#7C3AED",
            font=ctk.CTkFont(weight="bold"),
            command=self.send
        )
        self.send_btn.pack(side="left", padx=2)

        self.stop_btn = ctk.CTkButton(
            dock_actions,
            text="Stop",
            width=65,
            height=38,
            corner_radius=12,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            font=ctk.CTkFont(weight="bold"),
            command=self.stop,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=2)

    def _switchTo_chat_feed(self):
        if not self.is_chat_started:
            if hasattr(self, 'welcome_frame'):
                self.welcome_frame.destroy()
            self.chat_feed = ctk.CTkScrollableFrame(
                self.center_frame, corner_radius=12, fg_color="#13141A"
            )
            self.chat_feed.grid(row=0, column=0, sticky="nsew")
            self.chat_feed.grid_columnconfigure(0, weight=1)
            self.is_chat_started = True

    def _reset_to_welcome(self):
        if hasattr(self, 'chat_feed'):
            self.chat_feed.destroy()
        self.is_chat_started = False
        self._build_welcome_screen()

    # ---------------- BUBBLE RENDERING HELPERS ----------------
    def _create_message_bubble(self, sender: str, is_user: bool = False, is_tool: bool = False):
        bg_color = "#232430" if is_user else (CARD_BG if not is_tool else "#0F1015")
        align_side = "e" if is_user else "w"

        bubble = ctk.CTkFrame(
            self.chat_feed,
            corner_radius=14,
            fg_color=bg_color,
            border_width=1,
            border_color="#2A2B3A" if not is_user else BORDER_PURPLE
        )
        bubble.grid(sticky=align_side, pady=8, padx=10)

        header_color = "#A78BFA" if is_user else ("#38BDF8" if not is_tool else "#F59E0B")
        header = ctk.CTkLabel(bubble, text=sender, font=ctk.CTkFont(size=11, weight="bold"), text_color=header_color)
        header.pack(anchor="w", padx=14, pady=(10, 2))

        msg_label = ctk.CTkLabel(bubble, text="", font=ctk.CTkFont(size=13), wraplength=580, justify="left")
        msg_label.pack(anchor="w", padx=14, pady=(0, 10))

        return msg_label

    # ---------------- ACTIONS ----------------
    def send(self):
        text = self.entry.get().strip()
        if not text or (self.worker and self.worker.is_alive()):
            return

        self._switchTo_chat_feed()
        self.entry.delete(0, "end")

        # 1. Render User Message
        user_lbl = self._create_message_bubble("You", is_user=True)
        user_lbl.configure(text=text)

        # 2. Prepare Agent Message Container
        self.current_agent_label = self._create_message_bubble("Agent", is_user=False)

        self.stop_event.clear()
        self._set_busy(True)

        self.worker = threading.Thread(
            target=run_agent,
            args=(text, lambda t, x: self.events.put((t, x)), self.stop_event),
            daemon=True,
        )
        self.worker.start()

    def stop(self):
        self.stop_event.set()

    def _set_busy(self, busy):
        self.send_btn.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")

    # ---------------- EVENT POLLING ----------------
    def _poll_events(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "token" and self.current_agent_label:
                    curr_text = self.current_agent_label.cget("text")
                    self.current_agent_label.configure(text=curr_text + text)

                elif kind == "thought":
                    thought_lbl = self._create_message_bubble("Thought 💭", is_tool=True)
                    thought_lbl.configure(text=text, text_color="#A1A1AA")

                elif kind == "tool":
                    tool_lbl = self._create_message_bubble("Tool Execution 🛠️", is_tool=True)
                    tool_lbl.configure(text=text)

                elif kind == "error":
                    err_lbl = self._create_message_bubble("System Error ⚠", is_tool=True)
                    err_lbl.configure(text=text, text_color="#EF4444")
                    self._set_busy(False)

                elif kind == "done":
                    self._set_busy(False)

        except queue.Empty:
            pass
        self.after(50, self._poll_events)



if __name__ == "__main__":
    app = AgentApp()
    app.mainloop()