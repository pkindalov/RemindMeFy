import sys
import os
import json
import uuid
import datetime
from math import ceil

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QDateEdit, QTimeEdit, QLabel,
    QCheckBox, QSpinBox, QListWidget, QDialog, QSystemTrayIcon, QMenu, QStyle, QToolButton
)
from PyQt5.QtCore import QTimer, QDate, QTime, Qt, pyqtSignal
from PyQt5.QtGui import QIcon

# --- Note Class with Unique ID ---
class Note:
    def __init__(self, date_time, text, sticky=False, uid=None,
                 last_ext_reminder=None, pre_final_triggered=False, final_reminder_triggered=False):
        self.date_time = date_time
        self.text = text
        self.sticky = sticky
        self.uid = uid or str(uuid.uuid4())
        self.last_ext_reminder = last_ext_reminder
        self.pre_final_triggered = pre_final_triggered
        self.final_reminder_triggered = final_reminder_triggered

    def to_dict(self):
        return {
            'date_time': self.date_time.isoformat(),
            'text': self.text,
            'sticky': self.sticky,
            'uid': self.uid,
            'last_ext_reminder': self.last_ext_reminder.isoformat() if self.last_ext_reminder else None,
            'pre_final_triggered': self.pre_final_triggered,
            'final_reminder_triggered': self.final_reminder_triggered
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
        return cls(dt, text, sticky, uid, lr, pft, frt)

# --- StickyNoteWindow Class ---
class StickyNoteWindow(QWidget):
    closed = pyqtSignal(object)  # Emits the note when closed.
    def __init__(self, note):
        super().__init__(None)  # No parent so the window remains independent.
        self.note = note
        self.setWindowTitle("Sticky: " + (note.text[:15] + "..." if len(note.text) > 15 else note.text))
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #FFFB88; border: 2px solid #E6A800;")
        layout = QVBoxLayout()
        self.text_label = QLabel(note.text)
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        self.setLayout(layout)
        self.resize(200, 200)
        self._drag_pos = None

    def update_text(self, new_text):
        self.text_label.setText(new_text)
        self.setWindowTitle("Sticky: " + (new_text[:15] + "..." if len(new_text) > 15 else new_text))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def closeEvent(self, event):
        self.closed.emit(self.note)
        event.accept()

# --- ReminderDialog Class ---
class ReminderDialog(QDialog):
    def __init__(self, note, reminder_type):
        super().__init__()
        self.setWindowTitle("Reminder")
        layout = QVBoxLayout()
        if reminder_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.date_time.strftime('%H:%M')}"
        elif reminder_type == "pre-final":
            msg = (f"Pre-Final Reminder (10 min before event):\n{note.text}\n"
                   f"Time: {(note.date_time - datetime.timedelta(minutes=10)).strftime('%H:%M')}")
        else:
            msg = f"Reminder:\n{note.text}"
        layout.addWidget(QLabel(msg))
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self.accept)
        layout.addWidget(dismiss)
        self.setLayout(layout)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

# --- MainWindow Class ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RemindMeFy")
        self.app_start_time = datetime.datetime.now()
        self.notes = []
        self.load_notes()
        self.settings = {"startup": False, "days_earlier": 2, "ext_reminder_interval_hours": 4}
        self.load_settings()
        self.current_note_uid = None  # Store uid of the currently selected note.
        self.sorting_enabled = False
        self.displayed_notes = []
        self.sticky_windows = {}         # Persistent sticky windows, keyed by note.uid.
        self.preview_sticky_window = None  # Preview window for new notes.
        self.init_ui()
        self.init_tray_icon()
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
        # Sticky checkbox: immediately create sticky window when toggled.
        self.sticky_checkbox = QCheckBox("Sticky Note")
        self.sticky_checkbox.toggled.connect(self.on_sticky_checkbox_toggled)
        notes_layout.addWidget(self.sticky_checkbox)
        # Reminder labels:
        self.next_reminder_label = QLabel("N/A")
        notes_layout.addWidget(self.next_reminder_label)
        self.pre_final_label = QLabel("")
        notes_layout.addWidget(self.pre_final_label)
        btn_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Note")
        self.add_button.clicked.connect(self.add_note)
        btn_layout.addWidget(self.add_button)
        self.update_button = QPushButton("Update Note")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.update_note)
        btn_layout.addWidget(self.update_button)
        self.delete_button = QPushButton("Delete Note")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_note)
        btn_layout.addWidget(self.delete_button)
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(self.clear_selection)
        btn_layout.addWidget(self.clear_button)
        notes_layout.addLayout(btn_layout)
        # Saved notes list and sort toggle.
        saved_notes_layout = QHBoxLayout()
        saved_notes_label = QLabel("Saved Notes:")
        saved_notes_layout.addWidget(saved_notes_label)
        self.sort_button = QToolButton()
        self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self.sort_button.setToolTip("Turn sorting ON")
        self.sort_button.clicked.connect(self.toggle_sorting)
        saved_notes_layout.addWidget(self.sort_button)
        saved_notes_layout.addStretch()
        notes_layout.addLayout(saved_notes_layout)
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
        desc_startup = QLabel("If checked, RemindMeFy will automatically start when Windows boots.")
        desc_startup.setStyleSheet("font-size: 10pt; color: gray;")
        settings_layout.addWidget(desc_startup)
        settings_layout.addWidget(QLabel("Days earlier to start reminding:"))
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setMinimum(0)
        self.days_spinbox.setMaximum(30)
        self.days_spinbox.setValue(self.settings.get("days_earlier", 2))
        settings_layout.addWidget(self.days_spinbox)
        desc_days = QLabel("Defines how many days before the event reminders should begin.")
        desc_days.setStyleSheet("font-size: 10pt; color: gray;")
        settings_layout.addWidget(desc_days)
        settings_layout.addWidget(QLabel("Ext Reminder Frequency (hours):"))
        self.ext_interval_spinbox = QSpinBox()
        self.ext_interval_spinbox.setMinimum(1)
        self.ext_interval_spinbox.setMaximum(24)
        self.ext_interval_spinbox.setValue(self.settings.get("ext_reminder_interval_hours", 4))
        settings_layout.addWidget(self.ext_interval_spinbox)
        desc_ext = QLabel("Specifies how often (in hours) to send reminders during the reminder window.")
        desc_ext.setStyleSheet("font-size: 10pt; color: gray;")
        settings_layout.addWidget(desc_ext)
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
        print("Timer started with interval:", interval_ms, "ms")

    def get_sort_key(self, note):
        now = datetime.datetime.now()
        if note.date_time < now:
            return datetime.datetime.max
        computed_rem, _, _ = self.compute_next_reminder(note)
        return computed_rem if computed_rem is not None else note.date_time

    def update_notes_list(self):
        self.notes_list.clear()
        if self.sorting_enabled:
            now = datetime.datetime.now()
            upcoming = [note for note in self.notes if note.date_time >= now]
            passed = [note for note in self.notes if note.date_time < now]
            sorted_upcoming = sorted(upcoming, key=lambda note: self.get_sort_key(note))
            self.displayed_notes = sorted_upcoming + passed
            for note in self.displayed_notes:
                dt_str = note.date_time.strftime("%Y-%m-%d %H:%M")
                self.notes_list.addItem(f"{dt_str} - {note.text}")
        else:
            self.displayed_notes = self.notes
            for note in self.notes:
                dt_str = note.date_time.strftime("%Y-%m-%d %H:%M")
                self.notes_list.addItem(f"{dt_str} - {note.text}")

    def toggle_sorting(self):
        self.sorting_enabled = not self.sorting_enabled
        if self.sorting_enabled:
            self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
            self.sort_button.setToolTip("Turn sorting OFF")
        else:
            self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
            self.sort_button.setToolTip("Turn sorting ON")
        self.update_notes_list()

    def on_sticky_checkbox_toggled(self, checked):
        # Create or close a sticky window immediately when the checkbox is toggled.
        if checked:
            if self.current_note_uid:
                # Edit mode: use the note corresponding to current_note_uid.
                note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
                if note:
                    if note.uid in self.sticky_windows:
                        self.sticky_windows[note.uid].update_text(self.note_text.toPlainText())
                    else:
                        win = StickyNoteWindow(note)
                        win.closed.connect(self.on_sticky_window_closed)
                        win.show()
                        self.sticky_windows[note.uid] = win
            else:
                # New-note mode: create a preview sticky window.
                if self.preview_sticky_window is None:
                    preview_note = Note(datetime.datetime.now(), self.note_text.toPlainText(), sticky=True)
                    self.preview_sticky_window = StickyNoteWindow(preview_note)
                    self.preview_sticky_window.closed.connect(self.on_sticky_window_closed)
                    self.preview_sticky_window.show()
        else:
            # If unchecked, close the corresponding sticky window.
            if self.current_note_uid:
                note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
                if note and note.uid in self.sticky_windows:
                    self.sticky_windows[note.uid].close()
                    del self.sticky_windows[note.uid]
            else:
                if self.preview_sticky_window is not None:
                    self.preview_sticky_window.close()
                    self.preview_sticky_window = None

    def on_sticky_window_closed(self, note):
        # When a sticky window is closed manually, uncheck the sticky checkbox.
        self.sticky_checkbox.blockSignals(True)
        self.sticky_checkbox.setChecked(False)
        self.sticky_checkbox.blockSignals(False)
        if note.uid in self.sticky_windows:
            del self.sticky_windows[note.uid]
        if self.preview_sticky_window and self.preview_sticky_window.note.uid == note.uid:
            self.preview_sticky_window = None

    def add_note(self):
        dt = datetime.datetime.combine(self.date_edit.date().toPyDate(), self.time_edit.time().toPyTime())
        text = self.note_text.toPlainText().strip()
        sticky = self.sticky_checkbox.isChecked()
        if text:
            note = Note(dt, text, sticky=sticky)
            self.notes.append(note)
            self.update_notes_list()
            self.note_text.clear()
            self.clear_selection()
            self.save_notes()
            if sticky:
                win = StickyNoteWindow(note)
                win.closed.connect(self.on_sticky_window_closed)
                win.show()
                self.sticky_windows[note.uid] = win
            if self.preview_sticky_window is not None:
                self.preview_sticky_window.close()
                self.preview_sticky_window = None

    def update_note(self):
        if self.current_note_uid:
            dt = datetime.datetime.combine(self.date_edit.date().toPyDate(), self.time_edit.time().toPyTime())
            text = self.note_text.toPlainText().strip()
            sticky = self.sticky_checkbox.isChecked()
            if text:
                note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
                if note is None:
                    return
                note.date_time = dt
                note.text = text
                note.sticky = sticky
                note.last_ext_reminder = None
                note.pre_final_triggered = False
                note.final_reminder_triggered = False
                self.update_notes_list()
                self.save_notes()
                self.clear_selection()
                if sticky:
                    if note.uid in self.sticky_windows:
                        self.sticky_windows[note.uid].update_text(text)
                    else:
                        win = StickyNoteWindow(note)
                        win.closed.connect(self.on_sticky_window_closed)
                        win.show()
                        self.sticky_windows[note.uid] = win
                else:
                    if note.uid in self.sticky_windows:
                        self.sticky_windows[note.uid].close()
                        del self.sticky_windows[note.uid]

    def delete_note(self):
        if self.current_note_uid:
            note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
            if note:
                self.notes = [n for n in self.notes if n.uid != note.uid]
                if note.uid in self.sticky_windows:
                    self.sticky_windows[note.uid].close()
                    del self.sticky_windows[note.uid]
            self.update_notes_list()
            self.clear_selection()
            self.save_notes()

    def clear_selection(self):
        self.notes_list.clearSelection()
        self.current_note_uid = None
        self.note_text.clear()
        self.date_edit.setDate(datetime.date.today())
        self.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
        self.next_reminder_label.setText("N/A")
        self.pre_final_label.setText("")
        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.sticky_checkbox.blockSignals(True)
        self.sticky_checkbox.setChecked(False)
        self.sticky_checkbox.blockSignals(False)
        if self.preview_sticky_window is not None:
            self.preview_sticky_window.close()
            self.preview_sticky_window = None

    def load_note_details(self, item):
        if self.sorting_enabled:
            index = self.notes_list.row(item)
            if 0 <= index < len(self.displayed_notes):
                note = self.displayed_notes[index]
                self.current_note_uid = note.uid
        else:
            index = self.notes_list.row(item)
            if 0 <= index < len(self.notes):
                note = self.notes[index]
                self.current_note_uid = note.uid
        if self.current_note_uid:
            note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
            if note is None:
                return
            self.date_edit.setDate(note.date_time.date())
            self.time_edit.setTime(QTime(note.date_time.hour, note.date_time.minute))
            self.note_text.setText(note.text)
            self.update_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            self.sticky_checkbox.blockSignals(True)
            self.sticky_checkbox.setChecked(note.sticky)
            self.sticky_checkbox.blockSignals(False)
            now = datetime.datetime.now()
            if note.date_time < now:
                self.next_reminder_label.setText("Event Passed")
                self.next_reminder_label.setStyleSheet("color: red;")
                self.pre_final_label.setText("")
            else:
                self.next_reminder_label.setStyleSheet("")
                next_rem, r_type, pre_final = self.compute_next_reminder(note)
                if next_rem:
                    if r_type == "ext":
                        self.next_reminder_label.setText("Next Reminder at " + next_rem.strftime("%Y-%m-%d %H:%M"))
                        self.pre_final_label.setText("Pre-Final at " + pre_final.strftime("%Y-%m-%d %H:%M"))
                    elif r_type == "pre-final":
                        self.next_reminder_label.setText("Pre-Final Reminder at " + next_rem.strftime("%H:%M"))
                        self.pre_final_label.setText("")
                    elif r_type == "final":
                        self.next_reminder_label.setText("Final Reminder at " + next_rem.strftime("%H:%M"))
                        self.pre_final_label.setText("")
                    else:
                        self.next_reminder_label.setText(next_rem.strftime("%Y-%m-%d %H:%M"))
                        self.pre_final_label.setText("")
                else:
                    self.next_reminder_label.setText("No upcoming reminder")
                    self.pre_final_label.setText("")

    def compute_next_reminder(self, note):
        now = datetime.datetime.now()
        target = note.date_time
        threshold = datetime.timedelta(minutes=10)
        pre_final_time = target - threshold
        ext_interval = datetime.timedelta(hours=self.settings.get("ext_reminder_interval_hours", 4))
        days_earlier = datetime.timedelta(days=self.settings.get("days_earlier", 2))
        if now >= target:
            return (target, "final", pre_final_time)
        if now >= pre_final_time:
            return (pre_final_time, "pre-final", pre_final_time)
        if target - now > days_earlier:
            return (None, None, pre_final_time)
        baseline = self.app_start_time
        if now < baseline:
            next_ext = baseline
        else:
            n = ceil((now - baseline).total_seconds() / ext_interval.total_seconds())
            next_ext = baseline + n * ext_interval
        if next_ext >= pre_final_time:
            return (pre_final_time, "pre-final", pre_final_time)
        return (next_ext, "ext", pre_final_time)

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
        temp_file = "notes.json.tmp"
        try:
            with open(temp_file, "w") as f:
                data = [note.to_dict() for note in self.notes]
                json.dump(data, f)
            os.replace(temp_file, "notes.json")
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
        self.settings["startup"] = self.startup_checkbox.isChecked()
        self.settings["ext_reminder_interval_hours"] = self.ext_interval_spinbox.value()
        self.settings["days_earlier"] = self.days_spinbox.value()
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
                winreg.SetValueEx(key, "RemindMeFy", 0, winreg.REG_SZ,
                                  f'"{exe_path}" "{script_path}"')
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
                next_rem, r_type, _ = self.compute_next_reminder(note)
                if next_rem and now >= next_rem:
                    if r_type == "pre-final" and not note.pre_final_triggered:
                        print(f"Triggering pre-final reminder for: {note.text} at {now}")
                        self.show_reminder(note, r_type)
                        note.pre_final_triggered = True
                    elif r_type == "ext":
                        print(f"Triggering ext reminder for: {note.text} at {now}")
                        self.show_reminder(note, r_type)
                        note.last_ext_reminder = now
            else:
                if not getattr(note, "final_reminder_triggered", False):
                    print(f"Event passed. Triggering final reminder for: {note.text} at {now}")
                    self.show_reminder(note, "final")
                    note.final_reminder_triggered = True
        self.save_notes()

    def show_reminder(self, note, r_type):
        if r_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.date_time.strftime('%H:%M')}"
        elif r_type == "ext":
            msg = f"Reminder:\n{note.text}\nEvent: {note.date_time.strftime('%Y-%m-%d %H:%M')}"
        elif r_type == "pre-final":
            msg = (f"Pre-Final Reminder:\n{note.text}\n"
                   f"Time: {(note.date_time - datetime.timedelta(minutes=10)).strftime('%H:%M')}")
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
