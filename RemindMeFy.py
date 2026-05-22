"""
RemindMeFy - A modern reminder application with customtkinter.

This application provides a modern, dark-themed GUI for managing reminders,
supporting various repeat modes, dynamic reminder intervals, and sticky notes.
"""

import datetime
import json
import os
import sys
import uuid
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

import customtkinter as ctk
import pystray
from PIL import Image
from pydantic import BaseModel, Field, ConfigDict

# -------------------------------
# Models
# -------------------------------

class NoteModel(BaseModel):
    """Data model for a reminder note.
    
    Attributes:
        uid: Unique identifier for the note.
        date_time: The scheduled date and time of the reminder.
        text: The content of the reminder.
        sticky: Whether the note should appear as a sticky window.
        last_ext_reminder: Timestamp of the last extended reminder.
        pre_final_triggered: Whether the 10-minute pre-final reminder has been triggered.
        final_reminder_triggered: Whether the final reminder has been triggered.
        reminder_days: Number of days before the event to start reminding.
        last_repeat_reminder_date: Last date a repeating reminder was shown.
        repeat_mode: Mode of repetition (None, Daily, Weekly, Monthly, Yearly, Custom).
        repeat_interval_hours: Interval in hours for Custom mode.
        repeat_interval_days: Interval in days for Custom mode.
        next_occurrence: The next upcoming occurrence of the reminder.
        last_daily_reminder_time: Last time a dynamic reminder was shown on the occurrence day.
        suppress_dynamic_reminders: If True, only the final and pre-final reminders are shown.
    """
    model_config = ConfigDict(strict=False, frozen=False)

    uid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date_time: datetime.datetime
    text: str
    sticky: bool = False
    last_ext_reminder: Optional[datetime.datetime] = None
    pre_final_triggered: bool = False
    final_reminder_triggered: bool = False
    reminder_days: int = 0
    last_repeat_reminder_date: Optional[datetime.date] = None
    repeat_mode: str = "None"
    repeat_interval_hours: Optional[int] = None
    repeat_interval_days: int = 0
    next_occurrence: datetime.datetime
    last_daily_reminder_time: Optional[datetime.datetime] = None
    suppress_dynamic_reminders: bool = False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NoteModel":
        """Load from dictionary with proper type conversion.
        
        Args:
            d: Dictionary containing note data.
            
        Returns:
            A NoteModel instance.
        """
        for field in ['date_time', 'next_occurrence', 'last_ext_reminder', 'last_daily_reminder_time']:
            if isinstance(d.get(field), str):
                d[field] = datetime.datetime.fromisoformat(d[field])
        if isinstance(d.get('last_repeat_reminder_date'), str):
            d['last_repeat_reminder_date'] = datetime.date.fromisoformat(d['last_repeat_reminder_date'])
        return cls(**d)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            A dictionary representation of the note.
        """
        d = self.model_dump()
        for field in ['date_time', 'next_occurrence', 'last_ext_reminder', 'last_daily_reminder_time']:
            if d[field]: d[field] = d[field].isoformat()
        if d['last_repeat_reminder_date']:
            d['last_repeat_reminder_date'] = d['last_repeat_reminder_date'].isoformat()
        return d

class SettingsModel(BaseModel):
    """Application settings model.
    
    Attributes:
        startup: Whether to start the application on Windows boot.
        days_earlier: Default days before an event to start showing reminders.
        ext_reminder_interval_hours: Frequency of reminders in hours.
    """
    startup: bool = False
    days_earlier: int = 2
    ext_reminder_interval_hours: int = 4

# -------------------------------
# Logic Helpers
# -------------------------------

def get_dynamic_interval(remaining: datetime.timedelta) -> datetime.timedelta:
    """Determine the next reminder interval based on remaining time to the event.
    
    Args:
        remaining: Time remaining until the occurrence.
        
    Returns:
        The timedelta interval for the next reminder.
    """
    if remaining > datetime.timedelta(hours=6): return datetime.timedelta(minutes=60)
    if remaining > datetime.timedelta(hours=2): return datetime.timedelta(minutes=30)
    if remaining > datetime.timedelta(hours=1): return datetime.timedelta(minutes=15)
    return datetime.timedelta(minutes=5)

def compute_next_occurrence(note: NoteModel) -> datetime.datetime:
    """Calculate the next occurrence of a repeating reminder.
    
    Args:
        note: The note for which to calculate the next occurrence.
        
    Returns:
        The calculated datetime of the next occurrence.
    """
    target = note.next_occurrence
    if note.repeat_mode == "Daily": return target + datetime.timedelta(days=1)
    if note.repeat_mode == "Weekly": return target + datetime.timedelta(weeks=1)
    if note.repeat_mode == "Monthly": return target + datetime.timedelta(days=30)
    if note.repeat_mode == "Yearly": return target + datetime.timedelta(days=365)
    if note.repeat_mode == "Custom":
        days = note.repeat_interval_days or 0
        hours = note.repeat_interval_hours or 0
        return target + datetime.timedelta(days=days, hours=hours)
    return target

# -------------------------------
# Core Manager
# -------------------------------

class NoteManager:
    """Manages note persistence and operational logic."""
    def __init__(self, storage_path: Path):
        """Initialize the NoteManager.
        
        Args:
            storage_path: Path to the JSON file for note storage.
        """
        self.storage_path = storage_path
        self.notes: List[NoteModel] = []
        self.load_notes()

    def load_notes(self) -> None:
        """Load notes from the storage path."""
        if not self.storage_path.exists(): return
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                self.notes = [NoteModel.from_dict(d) for d in data]
        except Exception as e:
            print(f"Error loading notes: {e}")

    def save_notes(self) -> None:
        """Save all current notes to the storage path atomically."""
        tmp_path = self.storage_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump([n.to_dict() for n in self.notes], f, indent=4)
            tmp_path.replace(self.storage_path)
        except Exception as e:
            print(f"Error saving notes: {e}")

# -------------------------------
# GUI Components
# -------------------------------

class ReminderPopup(ctk.CTkToplevel):
    """Modern reminder dialog."""
    def __init__(self, note: NoteModel, reminder_type: str):
        super().__init__()
        self.title("RemindMeFy - Reminder")
        self.geometry("400x250")
        self.attributes("-topmost", True)
        
        msg_map = {
            "final": f"Final Reminder:\n{note.text}\nTime: {note.next_occurrence.strftime('%H:%M')}",
            "pre-final": f"Pre-Final Reminder (10 min before):\n{note.text}",
            "ext": f"Reminder:\n{note.text}"
        }
        
        ctk.CTkLabel(self, text=msg_map.get(reminder_type, "Reminder"), wraplength=350, font=("Segoe UI", 14)).pack(pady=30, padx=20)
        ctk.CTkButton(self, text="Dismiss", command=self.destroy).pack(pady=20)

class StickyNote(ctk.CTkToplevel):
    """Floating sticky note."""
    def __init__(self, note: NoteModel, on_close_callback=None):
        super().__init__()
        self.note, self.on_close_callback = note, on_close_callback
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("200x200")
        self.configure(fg_color="#FFFB88")

        self.label = ctk.CTkLabel(self, text=note.text, wraplength=180, text_color="black")
        self.label.pack(expand=True, fill="both", padx=10, pady=10)
        
        ctk.CTkButton(self, text="Close", command=self.close_window, fg_color="#E6A800", hover_color="#B38600", text_color="black", height=20).pack(pady=5)

        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

    def start_move(self, event): self.x, self.y = event.x, event.y
    def do_move(self, event):
        self.geometry(f"+{self.winfo_x() + event.x - self.x}+{self.winfo_y() + event.y - self.y}")
    def close_window(self):
        if self.on_close_callback: self.on_close_callback(self.note.uid)
        self.destroy()

class RemindMeFyApp(ctk.CTk):
    """Main Application."""
    def __init__(self):
        super().__init__()
        self.title("RemindMeFy")
        self.geometry("1100x700")
        
        self.base_path = Path(__file__).parent
        self.note_manager = NoteManager(self.base_path / "notes.json")
        self.settings = self.load_settings()
        self.sticky_windows: Dict[str, StickyNote] = {}
        
        self.setup_ui()
        self.setup_tray()
        self.start_reminder_loop()
        self.show_dashboard()

    def load_settings(self) -> SettingsModel:
        path = self.base_path / "settings.json"
        if path.exists():
            try:
                with open(path, "r") as f: return SettingsModel(**json.load(f))
            except Exception: pass
        return SettingsModel()

    def save_settings(self):
        with open(self.base_path / "settings.json", "w") as f:
            json.dump(self.settings.model_dump(), f, indent=4)
        if sys.platform == "win32": self.update_windows_startup(self.settings.startup)

    def update_windows_startup(self, enable: bool):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, "RemindMeFy", 0, winreg.REG_SZ, f'"{sys.executable}" "{os.path.abspath(__file__)}"')
            else:
                try: winreg.DeleteValue(key, "RemindMeFy")
                except FileNotFoundError: pass
        except Exception as e: print(f"Startup error: {e}")

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="RemindMeFy", font=("Segoe UI", 20, "bold")).pack(pady=20)
        for name, cmd in [("Dashboard", self.show_dashboard), ("Add Note", self.show_add_note), 
                          ("Archive", self.show_archive), ("Settings", self.show_settings)]:
            ctk.CTkButton(self.sidebar, text=name, command=cmd).pack(pady=10, padx=20)
            
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def show_dashboard(self):
        self._clear_main()
        ctk.CTkLabel(self.main_container, text="Active Reminders", font=("Segoe UI", 24, "bold")).pack(pady=(0, 20), anchor="w")
        
        search_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 20))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self.render_notes(self.search_entry.get()))
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_container)
        self.scroll_frame.pack(fill="both", expand=True)
        self.render_notes()

    def render_notes(self, query: str = ""):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        now = datetime.datetime.now()
        
        notes = self.note_manager.notes
        if query: notes = [n for n in notes if query.lower() in n.text.lower()]
        
        for note in notes:
            if (self.main_container.winfo_children()[0].cget("text") == "Archive") == (note.next_occurrence < now and note.repeat_mode == "None"):
                self.create_card(note)

    def create_card(self, note: NoteModel):
        card = ctk.CTkFrame(self.scroll_frame)
        card.pack(fill="x", pady=5, padx=5)
        
        ctk.CTkLabel(card, text=f"{note.next_occurrence.strftime('%Y-%m-%d %H:%M')} | {note.repeat_mode}", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(card, text=note.text, wraplength=700, justify="left").pack(anchor="w", padx=10, pady=5)
        
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(actions, text="Edit", width=60, height=24, command=lambda n=note: self.show_add_note(n)).pack(side="right", padx=5)
        ctk.CTkButton(actions, text="Delete", width=60, height=24, fg_color="red", command=lambda u=note.uid: self.delete_note(u)).pack(side="right", padx=5)

    def show_add_note(self, note: Optional[NoteModel] = None):
        self._clear_main()
        ctk.CTkLabel(self.main_container, text="Edit Note" if note else "Add Note", font=("Segoe UI", 24, "bold")).pack(pady=(0, 20), anchor="w")
        
        form = ctk.CTkFrame(self.main_container)
        form.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Simple Date/Time Entry
        f1 = ctk.CTkFrame(form, fg_color="transparent")
        f1.pack(fill="x", pady=10)
        self.date_e = ctk.CTkEntry(f1, placeholder_text="YYYY-MM-DD", width=120)
        self.date_e.insert(0, note.date_time.strftime("%Y-%m-%d") if note else datetime.date.today().isoformat())
        self.date_e.pack(side="left", padx=10)
        self.time_e = ctk.CTkEntry(f1, placeholder_text="HH:MM", width=80)
        self.time_e.insert(0, note.date_time.strftime("%H:%M") if note else datetime.datetime.now().strftime("%H:%M"))
        self.time_e.pack(side="left")
        
        self.repeat_v = ctk.StringVar(value=note.repeat_mode if note else "None")
        ctk.CTkOptionMenu(form, values=["None", "Daily", "Weekly", "Monthly", "Yearly"], variable=self.repeat_v).pack(pady=10)
        
        self.txt = ctk.CTkTextbox(form, height=150)
        self.txt.insert("0.0", note.text if note else "")
        self.txt.pack(fill="x", padx=15, pady=10)
        
        self.sticky_v = ctk.BooleanVar(value=note.sticky if note else False)
        ctk.CTkCheckBox(form, text="Sticky Note", variable=self.sticky_v).pack(anchor="w", padx=20)
        
        ctk.CTkButton(form, text="Save", command=lambda: self.save_note(note)).pack(pady=20)

    def save_note(self, existing: Optional[NoteModel]):
        try:
            dt = datetime.datetime.strptime(f"{self.date_e.get()} {self.time_e.get()}", "%Y-%m-%d %H:%M")
            note = NoteModel(uid=existing.uid if existing else str(uuid.uuid4()), date_time=dt, text=self.txt.get("0.0", "end").strip(),
                             sticky=self.sticky_v.get(), repeat_mode=self.repeat_v.get(), next_occurrence=dt)
            if existing: self.note_manager.notes = [n if n.uid != note.uid else note for n in self.note_manager.notes]
            else: self.note_manager.notes.append(note)
            self.note_manager.save_notes()
            if note.sticky: self.show_sticky(note)
            self.show_dashboard()
        except Exception as e: print(f"Save error: {e}")

    def delete_note(self, uid: str):
        self.note_manager.notes = [n for n in self.note_manager.notes if n.uid != uid]
        self.note_manager.save_notes()
        if uid in self.sticky_windows: self.sticky_windows[uid].destroy()
        self.render_notes()

    def show_sticky(self, note: NoteModel):
        if note.uid in self.sticky_windows: self.sticky_windows[note.uid].destroy()
        self.sticky_windows[note.uid] = StickyNote(note, lambda u: self.sticky_windows.pop(u, None))

    def show_archive(self):
        self._clear_main()
        ctk.CTkLabel(self.main_container, text="Archive", font=("Segoe UI", 24, "bold")).pack(pady=(0, 20), anchor="w")
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_container)
        self.scroll_frame.pack(fill="both", expand=True)
        self.render_notes()

    def show_settings(self):
        self._clear_main()
        ctk.CTkLabel(self.main_container, text="Settings", font=("Segoe UI", 24, "bold")).pack(pady=(0, 20), anchor="w")
        c = ctk.CTkFrame(self.main_container)
        c.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.start_cb = ctk.CTkCheckBox(c, text="Start with Windows")
        if self.settings.startup: self.start_cb.select()
        self.start_cb.pack(pady=20, padx=20, anchor="w")
        
        ctk.CTkButton(c, text="Save Settings", command=self.apply_settings).pack(pady=20)

    def apply_settings(self):
        self.settings.startup = bool(self.start_cb.get())
        self.save_settings()

    def _clear_main(self):
        for w in self.main_container.winfo_children(): w.destroy()

    # ---------------------------
    # Tray & Loop
    # ---------------------------
    def setup_tray(self):
        img = Image.open(self.base_path / "remindmefy.ico") if (self.base_path / "remindmefy.ico").exists() else Image.new('RGB', (64, 64), (73, 109, 137))
        self.tray = pystray.Icon("RemindMeFy", img, "RemindMeFy", pystray.Menu(pystray.MenuItem('Show', self.deiconify), pystray.MenuItem('Exit', self.quit_app)))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def quit_app(self):
        self.tray.stop()
        self.quit()

    def start_reminder_loop(self):
        def loop():
            while True:
                self.after(0, self.check_reminders)
                time.sleep(10)
        threading.Thread(target=loop, daemon=True).start()

    def check_reminders(self):
        now = datetime.datetime.now()
        for note in self.note_manager.notes:
            # Full Logic Parity
            if note.repeat_mode != "None" and now >= note.next_occurrence:
                note.next_occurrence = compute_next_occurrence(note)
                note.pre_final_triggered = note.final_reminder_triggered = False
                note.last_ext_reminder = note.last_daily_reminder_time = None
            
            threshold = datetime.timedelta(minutes=10)
            pre_final_time = note.next_occurrence - threshold
            
            if now >= note.next_occurrence and not note.final_reminder_triggered:
                self.trigger_reminder(note, "final")
                note.final_reminder_triggered = True
            elif now >= pre_final_time and not note.pre_final_triggered and now < note.next_occurrence:
                self.trigger_reminder(note, "pre-final")
                note.pre_final_triggered = True
            elif now < pre_final_time:
                # Dynamic/Ext logic
                interval = get_dynamic_interval(note.next_occurrence - now)
                last = note.last_daily_reminder_time or note.last_ext_reminder
                if not last or now >= last + interval:
                    if not note.suppress_dynamic_reminders:
                        self.trigger_reminder(note, "ext")
                        note.last_daily_reminder_time = now
        self.note_manager.save_notes()

    def trigger_reminder(self, note: NoteModel, r_type: str):
        self.tray.notify(note.text, f"RemindMeFy - {r_type.title()} Reminder")
        ReminderPopup(note, r_type)

if __name__ == "__main__":
    app = RemindMeFyApp()
    app.mainloop()
