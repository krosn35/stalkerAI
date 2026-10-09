"""CustomTkinter profile form centered in the window.

Fields (name, school, city) -> PersonProfile object.
The single "Name" field is split on whitespace: first word -> name, the rest -> surname.
"""
import os
from dataclasses import dataclass, asdict
import asyncio
import api
import customtkinter as ctk

BG_DARK = "#0D0E12"       # Window background
CARD_BG = "#1A1B23"       # Card background
BORDER_PURPLE = "#8B5CF6" # Accent highlight
TEXT_MUTED = "#8E8F9A"    # Muted labels

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
    """'Jan  Novák Svoboda' -> ('Jan', 'Novák Svoboda').

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
        self.geometry("700x640")
        self.minsize(480, 560)
        self.configure(fg_color=BG_DARK)

        self.profile = PersonProfile()
        self.profile_entries = {}

        # A single cell with weight=1 and no sticky -> the card stays centered
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.bind("<Return>", lambda e: self.save_profile())
        self.bind("<KP_Enter>", lambda e: self.save_profile())
        self._build_card()
        self._build_platform_card()

    def _build_card(self):
        card = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=BORDER_PURPLE
        )
        card.place(relx=0.5, y=40, anchor="n")

        def _build_platform_card(self):
            card = ctk.CTkFrame(
                self, fg_color=CARD_BG, corner_radius=20,
                border_width=1, border_color=BORDER_PURPLE
            )
            card.place(relx=0.5, y=420, anchor="n")

            ctk.CTkLabel(
                card, text="Search on", font=ctk.CTkFont(size=14, weight="bold")
            ).pack(padx=40, pady=(16, 8))

            self.platform_menu = ctk.CTkOptionMenu(
                card,
                values=["LinkedIn", "Instagram", "Both"],
                width=540,
                height=40,
                corner_radius=10,
                fg_color="#20212B",
                button_color=BORDER_PURPLE,
                button_hover_color="#7C3AED",
                font=ctk.CTkFont(size=14),
            )
            self.platform_menu.set("LinkedIn")
            self.platform_menu.pack(padx=40, pady=(0, 20))

        #INPUT CARD HEADING
        ctk.CTkLabel(
            card, text="🤖 StalkerAI", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=40, pady=(12, 2))
        ctk.CTkLabel(
            card, text="Profil", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED
        ).pack(pady=(0, 8))


        #INPUT CARD
        for field, placeholder in PROFILE_FIELDS:
            entry = ctk.CTkEntry(
                card,
                placeholder_text=placeholder,
                width=540,
                height=40,
                corner_radius=10,
                fg_color="#20212B",
                border_width=1,
                border_color="#2A2B36",
                font=ctk.CTkFont(size=14),

            )
            entry.pack(padx=40, pady=3)
            self.profile_entries[field] = entry

        #SPACE BETWEEN INPUT AND SAVE BUTTON
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(padx=40, pady=(16, 8), fill="x")
        buttons.grid_columnconfigure(0, weight=1)

        #INPUT SAVE BUTTON
        ctk.CTkButton(
            buttons, text="Save", height=40, corner_radius=10, width=340,
            fg_color=BORDER_PURPLE, hover_color="#7C3AED",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.save_profile
        ).grid(row=0, column=0, sticky="ew")

        self.status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            card, textvariable=self.status_var,
            font=ctk.CTkFont(size=12), text_color="#38BDF8"
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

        name = self.profile.to_dict()["name"]
        linkedin = asyncio.run(api.search_linkedin_accounts(name))
        instagram = asyncio.run(api.search_instagram_accounts(name))
        print("RAW LINKEDIN:", linkedin)
        print("RAW INSTAGRAM:", instagram)

        shown = self._show_results(linkedin or [], instagram or [])
        self.status_var.set(f"Found {shown} profile(s)")

    def clear_profile(self):
        for entry in self.profile_entries.values():
            entry.delete(0, "end")
        self.profile = PersonProfile()
        self.status_var.set("")
        self.focus()

    def _build_platform_card(self):
        self.results_card = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=BORDER_PURPLE
        )
        self.results_card.place(relx=0.5, y=420, anchor="n")

        ctk.CTkLabel(
            self.results_card, text="Found profiles",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(padx=40, pady=(16, 8))

        self.results_box = ctk.CTkScrollableFrame(
            self.results_card, width=540, height=160,
            fg_color="#20212B", corner_radius=10
        )
        self.results_box.pack(padx=40, pady=(0, 20))

        self.no_results_lbl = ctk.CTkLabel(
            self.results_box, text="No search yet", text_color=TEXT_MUTED
        )
        self.no_results_lbl.pack(pady=10)

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
            display = f"{name}  ({'@' + username})" if username else name
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

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    api.init()
    print(f".env test: {os.getenv('TEST')}")
    App().mainloop()