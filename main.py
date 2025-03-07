import sys
import os
import json
import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QDateTimeEdit, QLabel,
    QCheckBox, QSpinBox, QListWidget, QDialog
)
from PyQt5.QtCore import QTimer, QDateTime


# A simple Note class to hold each note's data.
class Note:
    def __init__(self, date_time, text, last_reminder=None):
        self.date_time = date_time  # datetime.datetime object
        self.text = text
        self.last_reminder = last_reminder  # datetime.datetime object

    def to_dict(self):
        return {
            'date_time': self.date_time.isoformat(),
            'text': self.text,
            'last_reminder': self.last_reminder.isoformat() if self.last_reminder else None,
        }

    @classmethod
    def from_dict(cls, d):
        date_time = datetime.datetime.fromisoformat(d['date_time'])
        text = d['text']
        last_reminder = datetime.datetime.fromisoformat(d['last_reminder']) if d['last_reminder'] else None
        return cls(date_time, text, last_reminder)


# A simple dialog that pops up as a reminder.
class ReminderDialog(QDialog):
    def __init__(self, note):
        super().__init__()
        self.note = note
        self.setWindowTitle("Reminder")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Reminder:"))
        layout.addWidget(QLabel(note.text))
        dismiss_button = QPushButton("Dismiss")
        dismiss_button.clicked.connect(self.accept)
        layout.addWidget(dismiss_button)
        self.setLayout(layout)


# The main window holds the tabs for notes and settings.
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RemindMeFy")
        self.notes = []
        self.load_notes()
        self.settings = {"startup": False, "days_earlier": 1}
        self.load_settings()
        self.current_edit_index = None  # To keep track of the note being edited
        self.init_ui()
        self.init_timer()

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Notes Tab ---
        self.notes_tab = QWidget()
        notes_layout = QVBoxLayout()

        # Date and Time picker with proper display format (including hours and minutes)
        notes_layout.addWidget(QLabel("Select Date and Time:"))
        self.date_time_edit = QDateTimeEdit()
        self.date_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.date_time_edit.setCalendarPopup(True)
        self.date_time_edit.setDateTime(QDateTime.currentDateTime())
        notes_layout.addWidget(self.date_time_edit)

        # Note text input
        notes_layout.addWidget(QLabel("Enter Note:"))
        self.note_text = QTextEdit()
        notes_layout.addWidget(self.note_text)

        # Buttons for adding, updating, and clearing selection
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Note")
        self.add_button.clicked.connect(self.add_note)
        button_layout.addWidget(self.add_button)

        self.update_button = QPushButton("Update Note")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.update_note)
        button_layout.addWidget(self.update_button)

        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(self.clear_selection)
        button_layout.addWidget(self.clear_button)

        notes_layout.addLayout(button_layout)

        # List of saved notes
        notes_layout.addWidget(QLabel("Saved Notes:"))
        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self.load_note_details)
        self.update_notes_list()
        notes_layout.addWidget(self.notes_list)

        self.notes_tab.setLayout(notes_layout)
        self.tabs.addTab(self.notes_tab, "Notes")

        # --- Settings Tab ---
        self.settings_tab = QWidget()
        settings_layout = QVBoxLayout()

        # Startup setting
        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(self.settings.get("startup", False))
        settings_layout.addWidget(self.startup_checkbox)

        # Days earlier setting
        settings_layout.addWidget(QLabel("Days earlier to start reminding:"))
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setMinimum(0)
        self.days_spinbox.setMaximum(30)
        self.days_spinbox.setValue(self.settings.get("days_earlier", 1))
        settings_layout.addWidget(self.days_spinbox)

        # Save settings button
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_settings_button)

        self.settings_tab.setLayout(settings_layout)
        self.tabs.addTab(self.settings_tab, "Settings")

    def update_notes_list(self):
        self.notes_list.clear()
        for note in self.notes:
            display_text = f"{note.date_time.strftime('%Y-%m-%d %H:%M')} - {note.text}"
            self.notes_list.addItem(display_text)

    def add_note(self):
        dt = self.date_time_edit.dateTime().toPyDateTime()
        text = self.note_text.toPlainText().strip()
        if text:
            new_note = Note(dt, text)
            self.notes.append(new_note)
            self.update_notes_list()
            self.note_text.clear()
            self.clear_selection()
            self.save_notes()

    def update_note(self):
        if self.current_edit_index is not None:
            dt = self.date_time_edit.dateTime().toPyDateTime()
            text = self.note_text.toPlainText().strip()
            if text:
                note = self.notes[self.current_edit_index]
                note.date_time = dt
                note.text = text
                note.last_reminder = None  # Reset reminder history on update
                self.update_notes_list()
                self.save_notes()
                self.clear_selection()

    def clear_selection(self):
        self.notes_list.clearSelection()
        self.current_edit_index = None
        self.note_text.clear()
        self.date_time_edit.setDateTime(QDateTime.currentDateTime())
        self.update_button.setEnabled(False)

    def load_note_details(self, item):
        index = self.notes_list.row(item)
        if index >= 0 and index < len(self.notes):
            self.current_edit_index = index
            note = self.notes[index]
            self.date_time_edit.setDateTime(QDateTime(note.date_time))
            self.note_text.setText(note.text)
            self.update_button.setEnabled(True)

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
        try:
            with open("notes.json", "w") as f:
                data = [note.to_dict() for note in self.notes]
                json.dump(data, f)
        except Exception as e:
            print("Error saving notes:", e)

    def load_settings(self):
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    self.settings = json.load(f)
            except Exception as e:
                print("Error loading settings:", e)
                self.settings = {"startup": False, "days_earlier": 1}

    def save_settings(self):
        self.settings["startup"] = self.startup_checkbox.isChecked()
        self.settings["days_earlier"] = self.days_spinbox.value()
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f)
        except Exception as e:
            print("Error saving settings:", e)
        # Set startup on Windows if needed
        if sys.platform.startswith('win'):
            self.set_startup(self.settings["startup"])

    def set_startup(self, enable):
        try:
            import winreg
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                # Create a registry entry to run this script at startup.
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

    def init_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(60000)  # Check every minute

    def check_reminders(self):
        now = datetime.datetime.now()
        days_earlier = self.settings.get("days_earlier", 1)
        for note in self.notes:
            note_time = note.date_time
            delta_days = (note_time.date() - now.date()).days
            if delta_days < 0:
                continue  # Skip notes already in the past
            if delta_days == 0:
                # On the day of the note, remind every hour if not already reminded this hour.
                if (note.last_reminder is None) or (note.last_reminder.hour != now.hour):
                    self.show_reminder(note)
                    note.last_reminder = now
            elif delta_days <= days_earlier:
                # In the reminder window (before the day of the note): remind once per day.
                if (note.last_reminder is None) or (note.last_reminder.date() != now.date()):
                    self.show_reminder(note)
                    note.last_reminder = now
        self.save_notes()

    def show_reminder(self, note):
        dlg = ReminderDialog(note)
        dlg.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
