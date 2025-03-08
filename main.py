import sys
import os
import json
import datetime
from math import ceil

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QDateEdit, QTimeEdit, QLabel,
    QCheckBox, QSpinBox, QListWidget, QDialog, QSystemTrayIcon, QMenu, QStyle
)
from PyQt5.QtCore import QTimer, QDate, QTime, Qt
from PyQt5.QtGui import QIcon

# Note class stores event data and ext reminder info.
class Note:
    def __init__(self, date_time, text, last_ext_reminder=None):
        self.date_time = date_time            # Target datetime for the note/event
        self.text = text                      # Note text
        self.last_ext_reminder = last_ext_reminder  # The last ext reminder time (if any)

    def to_dict(self):
        return {
            'date_time': self.date_time.isoformat(),
            'text': self.text,
            'last_ext_reminder': self.last_ext_reminder.isoformat() if self.last_ext_reminder else None
        }

    @classmethod
    def from_dict(cls, d):
        dt = datetime.datetime.fromisoformat(d['date_time'])
        text = d['text']
        lr = datetime.datetime.fromisoformat(d['last_ext_reminder']) if d.get('last_ext_reminder') else None
        return cls(dt, text, lr)

# A dialog to display the reminder.
class ReminderDialog(QDialog):
    def __init__(self, note, reminder_type):
        super().__init__()
        self.setWindowTitle("Reminder")
        layout = QVBoxLayout()
        if reminder_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.date_time.strftime('%H:%M')}"
        elif reminder_type == "ext":
            msg = f"Reminder:\n{note.text}\nEvent: {note.date_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            msg = f"Reminder:\n{note.text}"
        layout.addWidget(QLabel(msg))
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self.accept)
        layout.addWidget(dismiss)
        self.setLayout(layout)
        # Ensure the dialog appears on top.
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RemindMeFy")
        self.app_start_time = datetime.datetime.now()  # Record the app start time
        self.notes = []
        self.load_notes()
        # Settings: we use app_start_time for all events.
        # ext_reminder_interval_hours: how often to remind for events (default 4 hours)
        self.settings = {"startup": False, "ext_reminder_interval_hours": 4}
        self.load_settings()
        self.current_edit_index = None
        self.init_ui()
        self.init_tray_icon()
        # For testing, timer interval is 10 seconds; change to 60000 ms for production.
        self.init_timer(interval_ms=10000)

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        # --- Notes Tab ---
        self.notes_tab = QWidget()
        notes_layout = QVBoxLayout()
        dt_layout = QHBoxLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(datetime.date.today())
        dt_layout.addWidget(QLabel("Date:"))
        dt_layout.addWidget(self.date_edit)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
        dt_layout.addWidget(QLabel("Time:"))
        dt_layout.addWidget(self.time_edit)
        notes_layout.addLayout(dt_layout)
        notes_layout.addWidget(QLabel("Enter Note:"))
        self.note_text = QTextEdit()
        notes_layout.addWidget(self.note_text)
        # Only one dynamic Next Reminder label is kept.
        self.next_reminder_label = QLabel("N/A")
        notes_layout.addWidget(self.next_reminder_label)
        btn_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Note")
        self.add_button.clicked.connect(self.add_note)
        btn_layout.addWidget(self.add_button)
        self.update_button = QPushButton("Update Note")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.update_note)
        btn_layout.addWidget(self.update_button)
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(self.clear_selection)
        btn_layout.addWidget(self.clear_button)
        notes_layout.addLayout(btn_layout)
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
        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(self.settings.get("startup", False))
        settings_layout.addWidget(self.startup_checkbox)
        settings_layout.addWidget(QLabel("Ext Reminder Frequency (hours):"))
        self.ext_interval_spinbox = QSpinBox()
        self.ext_interval_spinbox.setMinimum(1)
        self.ext_interval_spinbox.setMaximum(24)
        self.ext_interval_spinbox.setValue(self.settings.get("ext_reminder_interval_hours", 4))
        settings_layout.addWidget(self.ext_interval_spinbox)
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_settings_button)
        self.settings_tab.setLayout(settings_layout)
        self.tabs.addTab(self.settings_tab, "Settings")

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self.style().standardIcon(QStyle.SP_ComputerIcon), self)
        self.tray_icon.setToolTip("RemindMeFy")
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Restore")
        restore_action.triggered.connect(self.show_normal)
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def init_timer(self, interval_ms=60000):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(interval_ms)

    def update_notes_list(self):
        self.notes_list.clear()
        for note in self.notes:
            dt_str = note.date_time.strftime("%Y-%m-%d %H:%M")
            self.notes_list.addItem(f"{dt_str} - {note.text}")

    def add_note(self):
        dt = datetime.datetime.combine(self.date_edit.date().toPyDate(), self.time_edit.time().toPyTime())
        text = self.note_text.toPlainText().strip()
        if text:
            note = Note(dt, text)
            self.notes.append(note)
            self.update_notes_list()
            self.note_text.clear()
            self.clear_selection()
            self.save_notes()

    def update_note(self):
        if self.current_edit_index is not None:
            dt = datetime.datetime.combine(self.date_edit.date().toPyDate(), self.time_edit.time().toPyTime())
            text = self.note_text.toPlainText().strip()
            if text:
                note = self.notes[self.current_edit_index]
                note.date_time = dt
                note.text = text
                note.last_ext_reminder = None
                self.update_notes_list()
                self.save_notes()
                self.clear_selection()

    def clear_selection(self):
        self.notes_list.clearSelection()
        self.current_edit_index = None
        self.note_text.clear()
        self.date_edit.setDate(datetime.date.today())
        self.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
        self.next_reminder_label.setText("N/A")
        self.update_button.setEnabled(False)

    def load_note_details(self, item):
        index = self.notes_list.row(item)
        if 0 <= index < len(self.notes):
            self.current_edit_index = index
            note = self.notes[index]
            self.date_edit.setDate(note.date_time.date())
            self.time_edit.setTime(QTime(note.date_time.hour, note.date_time.minute))
            self.note_text.setText(note.text)
            self.update_button.setEnabled(True)
            next_rem, r_type = self.compute_next_reminder(note)
            if next_rem:
                if r_type == "ext":
                    self.next_reminder_label.setText("Next Reminder at " + next_rem.strftime("%Y-%m-%d %H:%M"))
                elif r_type == "final":
                    self.next_reminder_label.setText("Final Reminder at " + next_rem.strftime("%H:%M"))
                else:
                    self.next_reminder_label.setText(next_rem.strftime("%Y-%m-%d %H:%M"))
            else:
                self.next_reminder_label.setText("No upcoming reminder")

    def compute_next_reminder(self, note):
        """
        Uses the app start time as baseline for all ext reminders.
        - If the event is within 10 minutes from now, returns (event time, "final").
        - Otherwise, computes:
             next_ext = app_start_time + n × (ext_reminder_interval)
          with n being the smallest integer such that next_ext > now.
        - If next_ext is later than the event, returns the event time as final reminder.
        """
        now = datetime.datetime.now()
        target = note.date_time
        threshold = datetime.timedelta(minutes=10)
        ext_interval = datetime.timedelta(hours=self.settings.get("ext_reminder_interval_hours", 4))
        # If event is within 10 minutes, final reminder.
        if target - now <= threshold:
            return (target, "final")
        baseline = self.app_start_time
        if now < baseline:
            next_ext = baseline
        else:
            n = ceil((now - baseline).total_seconds() / ext_interval.total_seconds())
            next_ext = baseline + n * ext_interval
        if next_ext >= target:
            return (target, "final")
        return (next_ext, "ext")

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
                if "ext_reminder_interval_hours" not in self.settings:
                    self.settings["ext_reminder_interval_hours"] = 4
            except Exception as e:
                print("Error loading settings:", e)
                self.settings = {"startup": False, "ext_reminder_interval_hours": 4}
        else:
            self.settings = {"startup": False, "ext_reminder_interval_hours": 4}

    def save_settings(self):
        self.settings["startup"] = self.startup_checkbox.isChecked()
        self.settings["ext_reminder_interval_hours"] = self.ext_interval_spinbox.value()
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f)
        except Exception as e:
            print("Error saving settings:", e)
        if sys.platform.startswith("win"):
            self.set_startup(self.settings["startup"])

    def set_startup(self, enable):
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

    def check_reminders(self):
        now = datetime.datetime.now()
        for note in self.notes:
            if note.date_time > now:
                next_rem, r_type = self.compute_next_reminder(note)
                if next_rem and now >= next_rem:
                    self.show_reminder(note, r_type)
                    note.last_ext_reminder = now
        self.save_notes()

    def show_reminder(self, note, r_type):
        if r_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.date_time.strftime('%H:%M')}"
        elif r_type == "ext":
            msg = f"Reminder:\n{note.text}\nEvent: {note.date_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            msg = f"Reminder:\n{note.text}"
        self.tray_icon.showMessage("RemindMeFy Reminder", msg, QSystemTrayIcon.Information, 10000)
        if not self.isVisible():
            self.show_normal()
        dlg = ReminderDialog(note, r_type)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
