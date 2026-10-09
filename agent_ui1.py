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

    def _build_card(self):
        card = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=BORDER_PURPLE
        )
        card.grid(row=0, column=0)  # centered

        ctk.CTkLabel(
            card, text="🤖 StalkerAI", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=40, pady=(28, 2))
        ctk.CTkLabel(
            card, text="Profil", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED
        ).pack(pady=(0, 18))

        for field, placeholder in PROFILE_FIELDS:
            entry = ctk.CTkEntry(
                card,
                placeholder_text=placeholder,
                width=340,
                height=40,
                corner_radius=10,
                fg_color="#20212B",
                border_width=1,
                border_color="#2A2B36",
                font=ctk.CTkFont(size=14),
            )
            entry.pack(padx=40, pady=5)
            self.profile_entries[field] = entry

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(padx=40, pady=(16, 8), fill="x")
        buttons.grid_columnconfigure(0, weight=1)

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
        self.status_var.set("Profile saved")
        print(asyncio.run(api.search_linkedin_accounts(self.profile.to_dict()["name"])))

    def clear_profile(self):
        for entry in self.profile_entries.values():
            entry.delete(0, "end")
        self.profile = PersonProfile()
        self.status_var.set("")
        self.focus()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    api.init()
    print(f".env test: {os.getenv('TEST')}")
    App().mainloop()