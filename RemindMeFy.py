import sys, os, json, uuid, datetime, threading
from math import ceil
import customtkinter as ctk
from tkinter import messagebox, scrolledtext
import tkinter as tk
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
import datetime

# Set theme for CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# -------------------------------
# Extended Note Class (with repeat fields and suppression flag)
# -------------------------------
class Note:
    def __init__(self, date_time, text, sticky=False, uid=None,
                 last_ext_reminder=None, pre_final_triggered=False, final_reminder_triggered=False,
                 reminder_days=0, last_repeat_reminder_date=None,
                 repeat_mode="None", repeat_interval_hours=None, repeat_interval_days=0,
                 next_occurrence=None, last_daily_reminder_time=None,
                 suppress_dynamic_reminders=False):
        self.date_time = date_time
        self.text = text
        self.sticky = sticky
        self.uid = uid or str(uuid.uuid4())
        self.last_ext_reminder = last_ext_reminder
        self.pre_final_triggered = pre_final_triggered
        self.final_reminder_triggered = final_reminder_triggered
        self.reminder_days = reminder_days
        self.last_repeat_reminder_date = last_repeat_reminder_date
        self.repeat_mode = repeat_mode
        self.repeat_interval_hours = repeat_interval_hours
        self.repeat_interval_days = repeat_interval_days
        self.next_occurrence = next_occurrence if next_occurrence else date_time
        self.last_daily_reminder_time = last_daily_reminder_time
        self.suppress_dynamic_reminders = suppress_dynamic_reminders

    def to_dict(self):
        return {
            'date_time': self.date_time.isoformat(),
            'text': self.text,
            'sticky': self.sticky,
            'uid': self.uid,
            'last_ext_reminder': self.last_ext_reminder.isoformat() if self.last_ext_reminder else None,
            'pre_final_triggered': self.pre_final_triggered,
            'final_reminder_triggered': self.final_reminder_triggered,
            'reminder_days': self.reminder_days,
            'last_repeat_reminder_date': self.last_repeat_reminder_date.isoformat() if self.last_repeat_reminder_date else None,
            'repeat_mode': self.repeat_mode,
            'repeat_interval_hours': self.repeat_interval_hours,
            'repeat_interval_days': self.repeat_interval_days,
            'next_occurrence': self.next_occurrence.isoformat(),
            'last_daily_reminder_time': self.last_daily_reminder_time.isoformat() if self.last_daily_reminder_time else None,
            'suppress_dynamic_reminders': self.suppress_dynamic_reminders
        }

    @classmethod
    def from_dict(cls, d):
        dt = datetime.datetime.fromisoformat(d['date_time'])
        text = d['text']
        sticky = d.get('sticky', False)
        uid = d.get('uid')
        lr = datetime.datetime.fromisoformat(d['last_ext_reminder']) if d.get('last_ext_reminder') else None
        pft = d.get('pre_final_triggered', False)
        frt = d.get('final_reminder_triggered', False)
        r_days = d.get('reminder_days', 0)
        last_repeat = None
        if d.get('last_repeat_reminder_date'):
            last_repeat = datetime.date.fromisoformat(d['last_repeat_reminder_date'])
        repeat_mode = d.get('repeat_mode', "None")
        repeat_interval_hours = d.get('repeat_interval_hours')
        repeat_interval_days = d.get('repeat_interval_days', 0)
        next_occurrence = datetime.datetime.fromisoformat(d['next_occurrence']) if d.get('next_occurrence') else dt
        last_daily = None
        if d.get('last_daily_reminder_time'):
            last_daily = datetime.datetime.fromisoformat(d['last_daily_reminder_time'])
        suppress = d.get('suppress_dynamic_reminders', False)
        return cls(dt, text, sticky, uid, lr, pft, frt, r_days, last_repeat,
                   repeat_mode, repeat_interval_hours, repeat_interval_days,
                   next_occurrence, last_daily, suppress)

# -------------------------------
# Sticky Note Window
# -------------------------------
class StickyNoteWindow:
    def __init__(self, note, on_close_callback):
        self.note = note
        self.on_close_callback = on_close_callback
        self.window = ctk.CTkToplevel()
        self.window.title("Sticky: " + (note.text[:15] + "..." if len(note.text) > 15 else note.text))
        self.window.geometry("250x200")
        self.window.configure(bg_color="#FFFB88", fg_color="#FFFB88")
        
        # Text label
        text_label = ctk.CTkLabel(
            self.window,
            text=note.text,
            text_color="#000000",
            wraplength=220,
            font=("Arial", 10),
            fg_color="#FFFB88",
            bg_color="#FFFB88"
        )
        text_label.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Close button
        close_btn = ctk.CTkButton(
            self.window,
            text="Close",
            command=self.close,
            width=100,
            fg_color="#E6A800",
            text_color="#000000"
        )
        close_btn.pack(pady=5)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._drag_pos = None
        self.window.bind("<Button-1>", self.on_mouse_press)
        self.window.bind("<B1-Motion>", self.on_mouse_drag)
        self.window.bind("<ButtonRelease-1>", self.on_mouse_release)

    def update_text(self, new_text):
        self.note.text = new_text
        self.window.title("Sticky: " + (new_text[:15] + "..." if len(new_text) > 15 else new_text))

    def on_mouse_press(self, event):
        self._drag_pos = (event.x_root - self.window.winfo_x(), event.y_root - self.window.winfo_y())

    def on_mouse_drag(self, event):
        if self._drag_pos:
            x = event.x_root - self._drag_pos[0]
            y = event.y_root - self._drag_pos[1]
            self.window.geometry(f"+{x}+{y}")

    def on_mouse_release(self, event):
        self._drag_pos = None

    def close(self):
        self.window.destroy()
        self.on_close_callback(self.note)

# -------------------------------
# Reminder Dialog
# -------------------------------
class ReminderDialog:
    def __init__(self, parent, note, reminder_type):
        self.note = note
        self.reminder_type = reminder_type
        self.window = ctk.CTkToplevel(parent)
        self.window.title("RemindMeFy Reminder")
        self.window.geometry("400x250")
        self.window.attributes('-topmost', True)
        
        # Icon/title
        title_label = ctk.CTkLabel(
            self.window,
            text=f"🔔 {reminder_type.upper()} REMINDER",
            font=("Arial", 14, "bold"),
            text_color="#FF9500"
        )
        title_label.pack(pady=15)
        
        # Message
        if reminder_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.next_occurrence.strftime('%H:%M')}"
        elif reminder_type == "pre-final":
            msg = (
                f"Pre-Final Reminder (10 min before):\n{note.text}\n"
                f"Time: {(note.next_occurrence - datetime.timedelta(minutes=10)).strftime('%H:%M')}"
            )
        else:
            msg = f"Reminder:\n{note.text}"
        
        msg_label = ctk.CTkLabel(
            self.window,
            text=msg,
            font=("Arial", 11),
            wraplength=350,
            justify="left"
        )
        msg_label.pack(pady=15, padx=20)
        
        # Dismiss button
        dismiss_btn = ctk.CTkButton(
            self.window,
            text="Dismiss",
            command=self.window.destroy,
            width=150,
            height=40,
            font=("Arial", 12, "bold")
        )
        dismiss_btn.pack(pady=15)

# -------------------------------
# Main Window
# -------------------------------
class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RemindMeFy - Professional Reminder Manager")
        self.geometry("1000x700")
        
        # Initialize data
        self.notes = []
        self.load_notes()
        self.settings = {"startup": False, "days_earlier": 2, "ext_reminder_interval_hours": 4}
        self.load_settings()
        
        self.current_note_uid = None
        self.sorting_enabled = False
        self.archive_mode = False
        self.displayed_notes = []
        self.sticky_windows = {}
        self.preview_sticky_window = None
        
        # UI Setup
        self.init_ui()
        self.update_notes_list()
        
        # Timer for checking reminders
        self.init_timer()
        
        # Tray icon setup
        self.init_tray_icon()

    def init_ui(self):
        # Main container
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Tab view
        self.tabview = ctk.CTkTabview(main_container)
        self.tabview.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Notes tab
        self.notes_tab = self.tabview.add("📝 Notes")
        self.setup_notes_tab()
        
        # Settings tab
        self.settings_tab = self.tabview.add("⚙️ Settings")
        self.setup_settings_tab()

    def setup_notes_tab(self):
        # Top section - Date/Time inputs
        input_frame = ctk.CTkFrame(self.notes_tab, fg_color="#2b2b2b", corner_radius=10)
        input_frame.pack(fill="x", padx=15, pady=15)
        
        # Date and Time
        date_time_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        date_time_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(date_time_frame, text="Date:", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        self.date_entry = ctk.CTkEntry(date_time_frame, width=120, placeholder_text="YYYY-MM-DD")
        self.date_entry.pack(side="left", padx=5)
        self.date_entry.insert(0, datetime.date.today().isoformat())
        
        ctk.CTkLabel(date_time_frame, text="Time:", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        self.time_entry = ctk.CTkEntry(date_time_frame, width=100, placeholder_text="HH:MM")
        self.time_entry.pack(side="left", padx=5)
        self.time_entry.insert(0, datetime.datetime.now().strftime("%H:%M"))
        
        # Days to remind and Repeat mode
        config_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        config_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(config_frame, text="Days to Remind:", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        self.days_spinner = ctk.CTkEntry(config_frame, width=80)
        self.days_spinner.pack(side="left", padx=5)
        self.days_spinner.insert(0, "0")
        
        ctk.CTkLabel(config_frame, text="Repeat Mode:", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        self.repeat_combo = ctk.CTkComboBox(
            config_frame,
            values=["None", "Daily", "Weekly", "Monthly", "Yearly", "Custom"],
            width=120,
            command=self.on_repeat_mode_changed
        )
        self.repeat_combo.set("None")
        self.repeat_combo.pack(side="left", padx=5)
        
        # Custom repeat interval
        self.custom_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        self.custom_frame.pack(fill="x", padx=15, pady=10)
        self.custom_frame.pack_forget()
        
        ctk.CTkLabel(self.custom_frame, text="Custom Days:", font=("Arial", 11)).pack(side="left", padx=5)
        self.custom_days_spinner = ctk.CTkEntry(self.custom_frame, width=80)
        self.custom_days_spinner.pack(side="left", padx=5)
        self.custom_days_spinner.insert(0, "0")
        
        ctk.CTkLabel(self.custom_frame, text="Hours:", font=("Arial", 11)).pack(side="left", padx=5)
        self.custom_hours_spinner = ctk.CTkEntry(self.custom_frame, width=80)
        self.custom_hours_spinner.pack(side="left", padx=5)
        self.custom_hours_spinner.insert(0, "0")
        
        # Note text area
        note_label = ctk.CTkLabel(self.notes_tab, text="Note Text:", font=("Arial", 12, "bold"))
        note_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.note_text = ctk.CTkTextbox(self.notes_tab, height=120, corner_radius=8)
        self.note_text.pack(fill="both", padx=15, pady=5, expand=False)
        
        # Sticky checkbox
        self.sticky_var = ctk.BooleanVar(value=False)
        sticky_check = ctk.CTkCheckBox(
            self.notes_tab,
            text="Create as Sticky Note",
            variable=self.sticky_var,
            font=("Arial", 11),
            command=self.on_sticky_checkbox_toggled
        )
        sticky_check.pack(anchor="w", padx=15, pady=5)
        
        # Only final reminder checkbox
        self.only_final_var = ctk.BooleanVar(value=False)
        self.only_final_check = ctk.CTkCheckBox(
            self.notes_tab,
            text="Only Final Reminder (suppress frequent reminders)",
            variable=self.only_final_var,
            font=("Arial", 11),
            command=self.on_only_final_changed
        )
        self.only_final_check.pack(anchor="w", padx=15, pady=5)
        self.only_final_check.pack_forget()
        
        # Info labels
        self.next_reminder_label = ctk.CTkLabel(self.notes_tab, text="Next Reminder: N/A", font=("Arial", 10))
        self.next_reminder_label.pack(anchor="w", padx=15, pady=3)
        
        self.reminder_info_label = ctk.CTkLabel(self.notes_tab, text="Reminder Info: N/A", font=("Arial", 10))
        self.reminder_info_label.pack(anchor="w", padx=15, pady=3)
        
        # Buttons frame
        button_frame = ctk.CTkFrame(self.notes_tab, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=10)
        
        self.add_button = ctk.CTkButton(button_frame, text="➕ Add Note", command=self.add_note, width=120, height=35)
        self.add_button.pack(side="left", padx=5)
        
        self.update_button = ctk.CTkButton(button_frame, text="✏️ Update", command=self.update_note, width=120, height=35)
        self.update_button.pack(side="left", padx=5)
        self.update_button.configure(state="disabled")
        
        self.delete_button = ctk.CTkButton(button_frame, text="🗑️ Delete", command=self.delete_note, width=120, height=35, fg_color="#CC0000")
        self.delete_button.pack(side="left", padx=5)
        self.delete_button.configure(state="disabled")
        
        self.clear_button = ctk.CTkButton(button_frame, text="Clear", command=self.clear_selection, width=120, height=35)
        self.clear_button.pack(side="left", padx=5)
        
        # Control buttons
        control_frame = ctk.CTkFrame(self.notes_tab, fg_color="transparent")
        control_frame.pack(fill="x", padx=15, pady=5)
        
        self.sort_button = ctk.CTkButton(control_frame, text="📊 Sort", command=self.toggle_sorting, width=100, height=30)
        self.sort_button.pack(side="left", padx=5)
        
        self.archive_button = ctk.CTkButton(control_frame, text="📦 Archive", command=self.toggle_archive, width=100, height=30)
        self.archive_button.pack(side="left", padx=5)
        
        self.refresh_button = ctk.CTkButton(control_frame, text="🔄 Refresh", command=self.update_notes_list, width=100, height=30)
        self.refresh_button.pack(side="left", padx=5)
        
        # Notes list
        list_label = ctk.CTkLabel(self.notes_tab, text="Your Notes:", font=("Arial", 12, "bold"))
        list_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.notes_listbox = tk.Listbox(
            self.notes_tab,
            height=10,
            font=("Arial", 10),
            bg="#2b2b2b",
            fg="#ffffff",
            selectmode=tk.SINGLE,
            highlightthickness=0
        )
        self.notes_listbox.pack(fill="both", padx=15, pady=5, expand=True)
        self.notes_listbox.bind("<<ListboxSelect>>", self.on_note_selected)
        
        # Scrollbar for listbox
        scrollbar = ctk.CTkScrollbar(self.notes_tab, command=self.notes_listbox.yview)
        self.notes_listbox.config(yscrollcommand=scrollbar.set)

    def setup_settings_tab(self):
        settings_frame = ctk.CTkFrame(self.settings_tab, fg_color="transparent")
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title = ctk.CTkLabel(settings_frame, text="⚙️ Application Settings", font=("Arial", 14, "bold"))
        title.pack(anchor="w", pady=(0, 20))
        
        # Startup option
        self.startup_var = ctk.BooleanVar(value=self.settings.get("startup", False))
        startup_check = ctk.CTkCheckBox(
            settings_frame,
            text="Start RemindMeFy with Windows",
            variable=self.startup_var,
            font=("Arial", 11)
        )
        startup_check.pack(anchor="w", pady=10)
        
        desc_label = ctk.CTkLabel(
            settings_frame,
            text="If checked, RemindMeFy will automatically start when Windows boots.",
            font=("Arial", 9),
            text_color="gray"
        )
        desc_label.pack(anchor="w", padx=20, pady=(0, 10))
        
        # Days earlier
        days_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        days_frame.pack(fill="x", pady=15)
        
        ctk.CTkLabel(days_frame, text="Days earlier to start reminding:", font=("Arial", 11)).pack(side="left", padx=5)
        self.days_earlier_spinner = ctk.CTkEntry(days_frame, width=80)
        self.days_earlier_spinner.pack(side="left", padx=5)
        self.days_earlier_spinner.insert(0, str(self.settings.get("days_earlier", 2)))
        
        # Reminder frequency
        freq_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        freq_frame.pack(fill="x", pady=15)
        
        ctk.CTkLabel(freq_frame, text="Reminder frequency (hours):", font=("Arial", 11)).pack(side="left", padx=5)
        self.freq_spinner = ctk.CTkEntry(freq_frame, width=80)
        self.freq_spinner.pack(side="left", padx=5)
        self.freq_spinner.insert(0, str(self.settings.get("ext_reminder_interval_hours", 4)))
        
        # Save button
        save_btn = ctk.CTkButton(
            settings_frame,
            text="💾 Save Settings",
            command=self.save_settings,
            width=200,
            height=40,
            font=("Arial", 12, "bold")
        )
        save_btn.pack(pady=30)

    def on_repeat_mode_changed(self, choice):
        if choice == "Custom":
            self.custom_frame.pack(fill="x", padx=15, pady=10, after=self.repeat_combo.master)
        else:
            self.custom_frame.pack_forget()

    def on_sticky_checkbox_toggled(self):
        # Preview logic can be added here
        pass

    def on_only_final_changed(self):
        if self.current_note_uid:
            note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
            if note:
                note.suppress_dynamic_reminders = self.only_final_var.get()
                self.save_notes()

    def on_note_selected(self, event):
        selection = self.notes_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.displayed_notes):
                note = self.displayed_notes[index]
                self.load_note_details(note)

    def load_note_details(self, note):
        self.current_note_uid = note.uid
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, note.date_time.date().isoformat())
        
        self.time_entry.delete(0, "end")
        self.time_entry.insert(0, note.date_time.strftime("%H:%M"))
        
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", note.text)
        
        self.days_spinner.delete(0, "end")
        self.days_spinner.insert(0, str(note.reminder_days))
        self.repeat_combo.set(note.repeat_mode)
        
        if note.repeat_mode == "Custom":
            self.custom_days_spinner.delete(0, "end")
            self.custom_days_spinner.insert(0, str(note.repeat_interval_days))
            self.custom_hours_spinner.delete(0, "end")
            self.custom_hours_spinner.insert(0, str(note.repeat_interval_hours if note.repeat_interval_hours else 0))
        
        self.sticky_var.set(note.sticky)
        self.update_button.configure(state="normal")
        self.delete_button.configure(state="normal")
        
        now = datetime.datetime.now()
        if note.next_occurrence > now:
            nxt, rtype, _ = self.compute_next_reminder(note)
            nxt_str = nxt.strftime("%Y-%m-%d %H:%M") if nxt else "None"
            self.next_reminder_label.configure(text=f"Next Reminder: {nxt_str}")
        else:
            self.next_reminder_label.configure(text="Event Passed")
        
        if note.repeat_mode != "None":
            info = f"Repeat: {note.repeat_mode}"
            if note.repeat_mode == "Custom":
                info += f" ({note.repeat_interval_days}d/{note.repeat_interval_hours}h)"
            if now.date() == note.next_occurrence.date():
                self.only_final_check.pack(anchor="w", padx=15, pady=5)
                self.only_final_var.set(note.suppress_dynamic_reminders)
            else:
                self.only_final_check.pack_forget()
        else:
            info = "Non-repeating"
            self.only_final_check.pack_forget()
        
        self.reminder_info_label.configure(text=f"Reminder Info: {info}")

    def update_notes_list(self):
        self.notes_listbox.delete(0, "end")
        now = datetime.datetime.now()
        filtered = []
        
        for note in self.notes:
            if note.repeat_mode == "None":
                if note.reminder_days > 0:
                    window_end = note.date_time + datetime.timedelta(days=note.reminder_days - 1)
                else:
                    window_end = note.date_time
            else:
                window_end = note.next_occurrence
            
            if not self.archive_mode:
                if now <= window_end:
                    filtered.append(note)
            else:
                if now > window_end:
                    filtered.append(note)
        
        if self.sorting_enabled:
            filtered = sorted(filtered, key=lambda n: n.next_occurrence)
        
        self.displayed_notes = filtered
        
        for note in self.displayed_notes:
            if note.next_occurrence > now:
                nxt, rtype, _ = self.compute_next_reminder(note)
                next_str = nxt.strftime("%Y-%m-%d %H:%M") if nxt else "None"
                info = f"Next: {next_str}"
            else:
                if note.repeat_mode != "None":
                    dyn = self.get_dynamic_reminder(note)
                    next_str = dyn.strftime("%Y-%m-%d %H:%M") if dyn else "None"
                    info = f"Next Daily: {next_str}"
                else:
                    info = "Final Occurrence"
            
            occ_str = note.next_occurrence.strftime("%Y-%m-%d %H:%M")
            item_text = f"{occ_str} - {note.text} (Mode: {note.repeat_mode}; {info})"
            self.notes_listbox.insert("end", item_text)

    def toggle_sorting(self):
        self.sorting_enabled = not self.sorting_enabled
        self.sort_button.configure(
            text="📊 Sort ON" if self.sorting_enabled else "📊 Sort OFF"
        )
        self.update_notes_list()

    def toggle_archive(self):
        self.archive_mode = not self.archive_mode
        self.archive_button.configure(
            text="📦 Archive ON" if self.archive_mode else "📦 Archive OFF"
        )
        self.update_notes_list()

    def add_note(self):
        try:
            date_str = self.date_entry.get()
            time_str = self.time_entry.get()
            dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Error", "Invalid date or time format. Use YYYY-MM-DD and HH:MM")
            return
        
        text = self.note_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter note text")
            return
        
        sticky = self.sticky_var.get()
        r_days = int(self.days_spinner.get())
        repeat_mode = self.repeat_combo.get()
        
        if repeat_mode == "Custom":
            custom_days = int(self.custom_days_spinner.get())
            custom_hours = int(self.custom_hours_spinner.get())
        else:
            custom_days = 0
            custom_hours = None
        
        note = Note(dt, text, sticky=sticky, reminder_days=r_days,
                    repeat_mode=repeat_mode, repeat_interval_hours=custom_hours,
                    repeat_interval_days=custom_days)
        note.next_occurrence = dt
        self.notes.append(note)
        self.save_notes()
        self.update_notes_list()
        self.clear_selection()
        
        if sticky:
            win = StickyNoteWindow(note, self.on_sticky_window_closed)
            self.sticky_windows[note.uid] = win
        
        messagebox.showinfo("Success", "Note added successfully!")

    def update_note(self):
        if not self.current_note_uid:
            messagebox.showwarning("Warning", "Please select a note to update")
            return
        
        try:
            date_str = self.date_entry.get()
            time_str = self.time_entry.get()
            dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Error", "Invalid date or time format")
            return
        
        text = self.note_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter note text")
            return
        
        note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
        if not note:
            return
        
        sticky = self.sticky_var.get()
        r_days = int(self.days_spinner.get())
        repeat_mode = self.repeat_combo.get()
        
        if repeat_mode == "Custom":
            custom_days = int(self.custom_days_spinner.get())
            custom_hours = int(self.custom_hours_spinner.get())
        else:
            custom_days = 0
            custom_hours = None
        
        note.date_time = dt
        note.text = text
        note.sticky = sticky
        note.reminder_days = r_days
        note.repeat_mode = repeat_mode
        note.repeat_interval_days = custom_days
        note.repeat_interval_hours = custom_hours
        note.last_ext_reminder = None
        note.pre_final_triggered = False
        note.final_reminder_triggered = False
        note.next_occurrence = dt
        
        self.save_notes()
        self.update_notes_list()
        self.clear_selection()
        messagebox.showinfo("Success", "Note updated successfully!")

    def delete_note(self):
        if not self.current_note_uid:
            messagebox.showwarning("Warning", "Please select a note to delete")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this note?"):
            note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
            if note:
                self.notes = [n for n in self.notes if n.uid != note.uid]
                if note.uid in self.sticky_windows:
                    self.sticky_windows[note.uid].close()
                    del self.sticky_windows[note.uid]
            
            self.save_notes()
            self.update_notes_list()
            self.clear_selection()
            messagebox.showinfo("Success", "Note deleted successfully!")

    def clear_selection(self):
        self.notes_listbox.selection_clear(0, "end")
        self.current_note_uid = None
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, datetime.date.today().isoformat())
        self.time_entry.delete(0, "end")
        self.time_entry.insert(0, datetime.datetime.now().strftime("%H:%M"))
        self.note_text.delete("1.0", "end")
        self.days_spinner.delete(0, "end")
        self.days_spinner.insert(0, "0")
        self.repeat_combo.set("None")
        self.sticky_var.set(False)
        self.only_final_check.pack_forget()
        self.next_reminder_label.configure(text="Next Reminder: N/A")
        self.reminder_info_label.configure(text="Reminder Info: N/A")
        self.update_button.configure(state="disabled")
        self.delete_button.configure(state="disabled")

    def get_dynamic_reminder(self, note):
        now = datetime.datetime.now()
        target = note.next_occurrence
        remaining = target - now
        if remaining > datetime.timedelta(hours=6):
            interval = datetime.timedelta(minutes=60)
        elif remaining > datetime.timedelta(hours=2):
            interval = datetime.timedelta(minutes=30)
        elif remaining > datetime.timedelta(hours=1):
            interval = datetime.timedelta(minutes=15)
        else:
            interval = datetime.timedelta(minutes=5)
        if note.last_daily_reminder_time:
            next_time = note.last_daily_reminder_time + interval
        else:
            next_time = now
        pre_final = target - datetime.timedelta(minutes=10)
        if next_time > pre_final:
            return pre_final
        return next_time

    def compute_next_occurrence(self, note):
        target = note.next_occurrence
        if note.repeat_mode == "Daily":
            return target + datetime.timedelta(days=1)
        elif note.repeat_mode == "Weekly":
            return target + datetime.timedelta(weeks=1)
        elif note.repeat_mode == "Monthly":
            return target + datetime.timedelta(days=30)
        elif note.repeat_mode == "Yearly":
            return target + datetime.timedelta(days=365)
        elif note.repeat_mode == "Custom":
            days = note.repeat_interval_days if note.repeat_interval_days else 0
            hours = note.repeat_interval_hours if note.repeat_interval_hours else 0
            return target + datetime.timedelta(days=days, hours=hours)
        else:
            return target

    def compute_next_reminder(self, note):
        now = datetime.datetime.now()
        target = note.next_occurrence
        threshold = datetime.timedelta(minutes=10)
        pre_final_time = target - threshold
        if now < target:
            if note.repeat_mode != "None" and now.date() == target.date():
                if note.suppress_dynamic_reminders:
                    return (pre_final_time, "pre-final", pre_final_time)
                dyn = self.get_dynamic_reminder(note)
                if dyn >= pre_final_time:
                    return (pre_final_time, "pre-final", pre_final_time)
                return (dyn, "ext", pre_final_time)
            else:
                ext_interval = datetime.timedelta(hours=self.settings.get("ext_reminder_interval_hours", 4))
                days_earlier = self.settings.get("days_earlier", 2)
                window_start = target - datetime.timedelta(days=days_earlier)
                if now < window_start:
                    return (None, None, pre_final_time)
                if note.last_ext_reminder:
                    next_ext = note.last_ext_reminder + ext_interval
                else:
                    next_ext = window_start
                if next_ext < now:
                    elapsed = now - window_start
                    intervals = int(elapsed.total_seconds() // ext_interval.total_seconds()) + 1
                    next_ext = window_start + intervals * ext_interval
                if next_ext >= pre_final_time:
                    return (pre_final_time, "pre-final", pre_final_time)
                return (next_ext, "ext", pre_final_time)
        else:
            return (target, "final", pre_final_time)

    def check_reminders(self):
        now = datetime.datetime.now()
        for note in self.notes:
            if note.repeat_mode != "None" and now >= note.next_occurrence:
                note.next_occurrence = self.compute_next_occurrence(note)
                note.last_daily_reminder_time = None
                note.pre_final_triggered = False
                note.final_reminder_triggered = False
                note.last_ext_reminder = None
            
            nxt, rtype, _ = self.compute_next_reminder(note)
            if nxt and now >= nxt:
                if rtype == "pre-final" and not note.pre_final_triggered:
                    self.show_reminder(note, "pre-final")
                    note.pre_final_triggered = True
                elif rtype == "ext":
                    if note.repeat_mode != "None" and now.date() == note.next_occurrence.date():
                        if note.suppress_dynamic_reminders:
                            continue
                        dyn = self.get_dynamic_reminder(note)
                        if dyn and now >= dyn:
                            self.show_reminder(note, "ext")
                            note.last_daily_reminder_time = now
                    else:
                        self.show_reminder(note, "ext")
                        note.last_ext_reminder = now
            if note.repeat_mode == "None" and now >= note.next_occurrence:
                if not note.final_reminder_triggered:
                    self.show_reminder(note, "final")
                    note.final_reminder_triggered = True
        
        self.save_notes()
        self.update_notes_list()

    def show_reminder(self, note, r_type):
        reminder_dialog = ReminderDialog(self, note, r_type)

    def init_timer(self):
        def timer_loop():
            while True:
                self.check_reminders()
                import time
                time.sleep(10)
        
        timer_thread = threading.Thread(daemon=True, target=timer_loop)
        timer_thread.start()

    def init_tray_icon(self):
        # Create a simple icon
        def create_icon():
            image = Image.new('RGB', (64, 64), color=(0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse([10, 10, 54, 54], fill='blue')
            return image
        
        # Note: Pystray might require additional setup on Windows
        # This is a placeholder - you may need to implement this differently
        pass

    def on_sticky_window_closed(self, note):
        if note.uid in self.sticky_windows:
            del self.sticky_windows[note.uid]

    def load_notes(self):
        if os.path.exists("notes.json"):
            try:
                with open("notes.json", "r") as f:
                    data = json.load(f)
                    self.notes = [Note.from_dict(d) for d in data]
            except Exception as e:
                print("Error loading notes:", e)
                self.notes = []

    def save_notes(self):
        tmp = "notes.json.tmp"
        try:
            with open(tmp, "w") as f:
                json.dump([n.to_dict() for n in self.notes], f)
            os.replace(tmp, "notes.json")
        except Exception as e:
            print("Error saving notes:", e)

    def load_settings(self):
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    self.settings = json.load(f)
                if "ext_reminder_interval_hours" not in self.settings:
                    self.settings["ext_reminder_interval_hours"] = 4
                if "days_earlier" not in self.settings:
                    self.settings["days_earlier"] = 2
            except Exception as e:
                print("Error loading settings:", e)
                self.settings = {"startup": False, "ext_reminder_interval_hours": 4, "days_earlier": 2}
        else:
            self.settings = {"startup": False, "ext_reminder_interval_hours": 4, "days_earlier": 2}

    def save_settings(self):
        self.settings["startup"] = self.startup_var.get()
        self.settings["ext_reminder_interval_hours"] = int(self.freq_spinner.get())
        self.settings["days_earlier"] = int(self.days_earlier_spinner.get())
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f)
        except Exception as e:
            print("Error saving settings:", e)
        
        if sys.platform.startswith("win"):
            self.set_startup(self.settings["startup"])
        
        messagebox.showinfo("Success", "Settings saved successfully!")

    def set_startup(self, enable):
        if not sys.platform.startswith("win"):
            return
        try:
            import winreg
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                exe_path = sys.executable
                script_path = os.path.abspath(__file__)
                winreg.SetValueEx(key, "RemindMeFy", 0, winreg.REG_SZ, f'"{exe_path}" "{script_path}"')
            else:
                try:
                    winreg.DeleteValue(key, "RemindMeFy")
                except Exception:
                    pass
        except Exception as e:
            print("Error setting startup:", e)

# Main execution
if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
