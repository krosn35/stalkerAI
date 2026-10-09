"""CustomTkinter profile form, auto-sized to fit its content.

Fields (name, school, city) -> PersonProfile object.
The single "Name" field is split on whitespace: first word -> name, the rest -> surname.
"""
import os
import json
from dataclasses import dataclass, asdict
import asyncio
import api
import customtkinter as ctk

BG_DARK = "#0D0E12"       # Window background
CARD_BG = "#1A1B23"       # Card background
BORDER_PURPLE = "#8B5CF6" # Accent highlight
TEXT_MUTED = "#8E8F9A"    # Muted labels

CARD_PAD = 20   # horizontal padding inside every card
FIELD_W = 380   # width of entries / results box

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


@dataclass
class PersonProfile:
    """Output object produced by the form."""
    name: str = ""
    school: str = ""
    city: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# (entry key, placeholder shown in the entry)
PROFILE_FIELDS = [
    ("name", "Name"),
    ("school", "School (optional)"),
    ("city", "City (optional)"),
]


def split_name(full_name: str) -> tuple[str, str]:
    """'Jan Novák Svoboda' -> ('Jan', 'Novák Svoboda').

    split() without arguments handles any number of spaces/tabs and
    ignores leading/trailing whitespace, so extra spaces are never a problem.
    """
    parts = full_name.split()
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("StalkerAI")
        self.configure(fg_color=BG_DARK)

        self.profile = PersonProfile()
        self.profile_entries = {}
        self._last_json = None

        self.bind("<Return>", lambda e: self.save_profile())
        self.bind("<KP_Enter>", lambda e: self.save_profile())

        # Main grid container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(padx=16, pady=16, fill="both", expand=True)

        # Top row: Input card (left) and Results card (right)
        self._build_card(self.container, row=0, col=0)
        self._build_platform_card(self.container, row=0, col=1)

        # Bottom row: Output JSON card spanning both columns
        self._build_json_card(self.container, row=1, col=0, colspan=2)

        self._autosize()

    def _autosize(self):
        """Shrink/grow the window to exactly fit everything packed into it."""
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        self.geometry(f"{w}x{h}")
        self.minsize(w, h)

    def _build_card(self, parent, row, col):
        card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=BORDER_PURPLE
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        # INPUT CARD HEADING
        ctk.CTkLabel(
            card, text="🤖 StalkerAI", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=CARD_PAD, pady=(16, 2))
        ctk.CTkLabel(
            card, text="Profil", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED
        ).pack(pady=(0, 12))

        # INPUT CARD
        for field, placeholder in PROFILE_FIELDS:
            entry = ctk.CTkEntry(
                card,
                placeholder_text=placeholder,
                width=FIELD_W,
                height=50,
                corner_radius=10,
                fg_color="#20212B",
                border_width=1,
                border_color="#2A2B36",
                font=ctk.CTkFont(size=14),
            )
            entry.pack(padx=CARD_PAD, pady=4)
            self.profile_entries[field] = entry

        # SPACE BETWEEN INPUT AND SAVE BUTTON
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(padx=CARD_PAD, pady=(16, 8), fill="x")
        buttons.grid_columnconfigure(0, weight=1)

        # INPUT SAVE BUTTON
        ctk.CTkButton(
            buttons, text="Save", height=40, corner_radius=10,
            fg_color=BORDER_PURPLE, hover_color="#7C3AED",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.save_profile
        ).grid(row=0, column=0, sticky="ew")

        self.status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            card, textvariable=self.status_var,
            font=ctk.CTkFont(size=12), text_color=BORDER_PURPLE
        ).pack(pady=(0, 20))

    def get_profile(self) -> PersonProfile:
        """Read the form and return it as a PersonProfile object."""
        values = {k: e.get().strip() for k, e in self.profile_entries.items()}
        return PersonProfile(
            name=values["name"],
            school=values["school"],
            city=values["city"],
        )

    def save_profile(self):
        self.profile = self.get_profile()
        print(self.profile)
        print(self.profile.to_dict())
        self.status_var.set("Searching...")
        self.update()  # repaint the status before the blocking calls below

        profile_dict = self.profile.to_dict()
        linkedin = asyncio.run(api.search_linkedin_accounts(profile_dict))
        instagram = asyncio.run(api.search_instagram_accounts(profile_dict))
        print("RAW LINKEDIN:", linkedin)
        print("RAW INSTAGRAM:", instagram)

        shown = self._show_results(linkedin or [], instagram or [])
        self._update_overview(linkedin, instagram)
        self._update_json(linkedin, instagram)
        self.status_var.set(f"Found {shown} profile(s)")
        self._autosize()  # content height can change after a search

    def clear_profile(self):
        for entry in self.profile_entries.values():
            entry.delete(0, "end")
        self.profile = PersonProfile()
        self.status_var.set("")
        self.focus()

    def _build_platform_card(self, parent, row, col):
        self.results_card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=BORDER_PURPLE
        )
        self.results_card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(
            self.results_card, text="Found profiles",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(padx=CARD_PAD, pady=(16, 8))

        self.results_box = ctk.CTkScrollableFrame(
            self.results_card, width=FIELD_W, height=180,
            fg_color="#20212B", corner_radius=10
        )
        self.results_box.pack(padx=CARD_PAD, pady=(0, 16))

        self.no_results_lbl = ctk.CTkLabel(
            self.results_box, text="No search yet", text_color=TEXT_MUTED
        )
        self.no_results_lbl.pack(pady=10)

        ctk.CTkLabel(
            self.results_card, text="Overview", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=BORDER_PURPLE
        ).pack(anchor="w", padx=CARD_PAD, pady=(0, 2))

        self.overview_lbl = ctk.CTkLabel(
            self.results_card, text="No search yet", text_color=TEXT_MUTED,
            justify="left", anchor="w", wraplength=FIELD_W - 20
        )
        self.overview_lbl.pack(anchor="w", padx=CARD_PAD, pady=(0, 20))

    def _render_result_list(self, parent, results):
        url_keys = ("linkedin_url", "instagram_url", "url", "profileUrl", "link", "profile_url", "href")
        count = 0

        if not results:
            ctk.CTkLabel(parent, text="No profiles found", text_color=TEXT_MUTED).pack(pady=6)
            return 0

        for item in results:
            if isinstance(item, dict):
                name = item.get("name") or item.get("fullName") or item.get("title") or ""
                if not name.strip():
                    continue
                url = next((item[k] for k in url_keys if item.get(k)), "")
            else:
                name = str(item)
                url = ""

            count += 1
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=3)

            username = item.get("username") if isinstance(item, dict) else None
            display = f"{name}  (@{username})" if username else name
            ctk.CTkLabel(row, text=display, anchor="w").pack(side="left", padx=(4, 0))

            if url:
                link = ctk.CTkLabel(row, text="Open", text_color=BORDER_PURPLE, cursor="hand2")
                link.pack(side="right", padx=4)
                link.bind("<Button-1>", lambda e, u=url: os.system(f'xdg-open "{u}"'))
            else:
                ctk.CTkLabel(row, text="(no link)", text_color=TEXT_MUTED).pack(side="right", padx=4)

        return count

    def _show_results(self, linkedin, instagram):
        for widget in self.results_box.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.results_box, text="LinkedIn", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=BORDER_PURPLE
        ).pack(anchor="w", padx=6, pady=(8, 2))
        li_count = self._render_result_list(self.results_box, linkedin)

        ctk.CTkLabel(
            self.results_box, text="Instagram", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=BORDER_PURPLE
        ).pack(anchor="w", padx=6, pady=(14, 2))
        ig_count = self._render_result_list(self.results_box, instagram)

        return li_count + ig_count

    def _update_overview(self, linkedin, instagram):
        pieces = []
        for item in (linkedin or []) + (instagram or []):
            if isinstance(item, dict):
                info = (item.get("info") or "").strip()
                if info:
                    pieces.append(info)

        if not pieces:
            self.overview_lbl.configure(text="No additional info found.")
            return

        seen = []
        for p in pieces:
            if p not in seen:
                seen.append(p)
        self.overview_lbl.configure(text=" · ".join(seen))

    def _build_json_card(self, parent, row, col, colspan=1):
        self.json_card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=BORDER_PURPLE
        )
        self.json_card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")

        header = ctk.CTkFrame(self.json_card, fg_color="transparent")
        header.pack(padx=CARD_PAD, pady=(16, 8), fill="x")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Output (JSON)", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="Save to file", width=110, height=28, corner_radius=8,
            fg_color=BORDER_PURPLE, hover_color="#7C3AED",
            font=ctk.CTkFont(size=12), command=self._save_json
        ).grid(row=0, column=1, sticky="e")

        # Increased height from 180 -> 320 to make output vertically larger
        self.json_box = ctk.CTkTextbox(
            self.json_card, height=520,
            fg_color="#20212B", corner_radius=10,
            font=ctk.CTkFont(size=12, family="monospace")
        )
        self.json_box.pack(padx=CARD_PAD, pady=(0, 20), fill="x", expand=True)
        self.json_box.insert("1.0", "{}")
        self.json_box.configure(state="disabled")

    def _update_json(self, linkedin, instagram):
        data = {
            "profile": self.profile.to_dict(),
            "linkedin": linkedin or [],
            "instagram": instagram or [],
        }
        text = json.dumps(data, indent=2, ensure_ascii=False)

        self.json_box.configure(state="normal")
        self.json_box.delete("1.0", "end")
        self.json_box.insert("1.0", text)
        self.json_box.configure(state="disabled")
        self._last_json = text

    def _save_json(self):
        if not self._last_json:
            return
        path = os.path.join(os.getcwd(), "stalkerai_output.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._last_json)
        self.status_var.set(f"Saved to {path}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    api.init()
    print(f".env test: {os.getenv('TEST')}")
    App().mainloop()