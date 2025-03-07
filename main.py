import sys
import os
import json
import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QDateEdit, QTimeEdit, QLabel,
    QCheckBox, QSpinBox, QListWidget, QDialog, QSystemTrayIcon, QMenu, QStyle
)
from PyQt5.QtCore import QTimer, QDate, QTime, Qt
from PyQt5.QtGui import QIcon


# Note class with flags to ensure each reminder is triggered only once.
class Note:
    def __init__(self, date_time, text, pre_final_triggered=False, final_reminder_triggered=False):
        self.date_time = date_time  # The target datetime for the note
        self.text = text  # The note text
        self.pre_final_triggered = pre_final_triggered  # Has the pre-final reminder been triggered?
        self.final_reminder_triggered = final_reminder_triggered  # Has the final reminder been triggered?

    def to_dict(self):
        return {
            'date_time': self.date_time.isoformat(),
            'text': self.text,
            'pre_final_triggered': self.pre_final_triggered,
            'final_reminder_triggered': self.final_reminder_triggered
        }

    @classmethod
    def from_dict(cls, d):
        dt = datetime.datetime.fromisoformat(d['date_time'])
        text = d['text']
        pft = d.get('pre_final_triggered', False)
        frt = d.get('final_reminder_triggered', False)
        return cls(dt, text, pft, frt)


# A dialog to show the reminder (it forces itself on top)
class ReminderDialog(QDialog):
    def __init__(self, note, reminder_type):
        super().__init__()
        self.setWindowTitle("Reminder")
        layout = QVBoxLayout()
        if reminder_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.date_time.strftime('%H:%M')}"
        elif reminder_type == "pre-final":
            msg = f"Pre-Final Reminder (10 min before final):\n{note.text}\nFinal Time: {note.date_time.strftime('%H:%M')}"
        else:
            msg = f"Reminder:\n{note.text}"
        layout.addWidget(QLabel(msg))
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self.accept)
        layout.addWidget(dismiss)
        self.setLayout(layout)
        # Make sure the dialog appears on top
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RemindMeFy")
        self.notes = []
        self.load_notes()
        # (For now, settings are not used in the reminder logic for today’s notes.)
        self.settings = {"startup": False, "days_earlier": 1, "reminder_interval_hours": 1}
        self.load_settings()
        self.current_edit_index = None  # Index of the note being edited
        self.init_ui()
        self.init_tray_icon()
        # Use a 10-second timer for testing; change to 60000 for production.
        self.init_timer(interval_ms=10000)

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Notes Tab ---
        self.notes_tab = QWidget()
        notes_layout = QVBoxLayout()

        # Date and Time pickers
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

        # Note text input
        notes_layout.addWidget(QLabel("Enter Note:"))
        self.note_text = QTextEdit()
        notes_layout.addWidget(self.note_text)

        # Next Reminder label (for display)
        notes_layout.addWidget(QLabel("Next Reminder:"))
        self.next_reminder_label = QLabel("N/A")
        notes_layout.addWidget(self.next_reminder_label)

        # Buttons: Add, Update, Clear
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

        # List of saved notes
        notes_layout.addWidget(QLabel("Saved Notes:"))
        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self.load_note_details)
        self.update_notes_list()
        notes_layout.addWidget(self.notes_list)

        self.notes_tab.setLayout(notes_layout)
        self.tabs.addTab(self.notes_tab, "Notes")

        # --- Settings Tab (not used in reminder logic for today) ---
        self.settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(self.settings.get("startup", False))
        settings_layout.addWidget(self.startup_checkbox)
        settings_layout.addWidget(QLabel("Days earlier to start reminding (for future notes):"))
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setMinimum(0)
        self.days_spinbox.setMaximum(30)
        self.days_spinbox.setValue(self.settings.get("days_earlier", 1))
        settings_layout.addWidget(self.days_spinbox)
        settings_layout.addWidget(QLabel("Reminder frequency (hours) for non-note-day reminders:"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(1)
        self.interval_spinbox.setMaximum(24)
        self.interval_spinbox.setValue(self.settings.get("reminder_interval_hours", 1))
        settings_layout.addWidget(self.interval_spinbox)
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_settings_button)
        self.settings_tab.setLayout(settings_layout)
        self.tabs.addTab(self.settings_tab, "Settings")

    def init_tray_icon(self):
        # Use a standard icon for the tray
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
                # Reset reminder flags on update.
                note.pre_final_triggered = False
                note.final_reminder_triggered = False
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
            # For display: if the note is today, show the next reminder type and time.
            now = datetime.datetime.now()
            if note.date_time.date() == now.date():
                pre_final_time = note.date_time - datetime.timedelta(minutes=10)
                if now < pre_final_time:
                    self.next_reminder_label.setText("Pre-Final Reminder at " + pre_final_time.strftime("%H:%M"))
                elif now < note.date_time:
                    self.next_reminder_label.setText("Final Reminder at " + note.date_time.strftime("%H:%M"))
                else:
                    self.next_reminder_label.setText("No upcoming reminder")
            else:
                self.next_reminder_label.setText(
                    "Final Reminder scheduled at " + note.date_time.strftime("%Y-%m-%d %H:%M"))

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
                self.settings = {"startup": False, "days_earlier": 1, "reminder_interval_hours": 1}

    def save_settings(self):
        self.settings["startup"] = self.startup_checkbox.isChecked()
        self.settings["days_earlier"] = self.days_spinbox.value()
        self.settings["reminder_interval_hours"] = self.interval_spinbox.value()
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f)
        except Exception as e:
            print("Error saving settings:", e)
        # For Windows startup logic (if needed)
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
        # Loop through notes and trigger reminders only for notes set for today.
        for note in self.notes:
            if note.date_time.date() == now.date():
                pre_final_time = note.date_time - datetime.timedelta(minutes=10)
                # If we're in the 10-min window before the note time and pre-final not yet triggered:
                if now >= pre_final_time and now < note.date_time and not note.pre_final_triggered:
                    self.show_reminder(note, "pre-final")
                    note.pre_final_triggered = True
                # If we're at or past the note time and final reminder not yet triggered:
                if now >= note.date_time and not note.final_reminder_triggered:
                    self.show_reminder(note, "final")
                    note.final_reminder_triggered = True
        self.save_notes()

    def show_reminder(self, note, reminder_type):
        # Build a message for the system tray notification.
        if reminder_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.date_time.strftime('%H:%M')}"
        elif reminder_type == "pre-final":
            msg = f"Pre-Final Reminder (10 min before final):\n{note.text}\nFinal Time: {note.date_time.strftime('%H:%M')}"
        else:
            msg = f"Reminder:\n{note.text}"
        # Show the tray notification (even if the app is minimized)
        self.tray_icon.showMessage("RemindMeFy Reminder", msg, QSystemTrayIcon.Information, 10000)
        # If the main window is hidden, restore it.
        if not self.isVisible():
            self.show_normal()
        # Also show a dialog so the reminder is obvious.
        dlg = ReminderDialog(note, reminder_type)
        dlg.exec_()

    # For testing, we use a 10-second timer. In production, change the interval (e.g., to 60000 ms).
    # The timer calls check_reminders() repeatedly.


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
