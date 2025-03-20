import sys, os, json, uuid, datetime
from math import ceil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QDateEdit, QTimeEdit, QLabel, QCheckBox, QSpinBox,
    QListWidget, QListWidgetItem, QDialog, QSystemTrayIcon, QMenu, QStyle,
    QToolButton, QComboBox
)
from PyQt5.QtCore import QTimer, QDate, QTime, Qt, pyqtSignal
from PyQt5.QtGui import QIcon

# -------------------------------
# Extended Note Class (with repeat fields)
# -------------------------------
class Note:
    def __init__(self, date_time, text, sticky=False, uid=None,
                 last_ext_reminder=None, pre_final_triggered=False, final_reminder_triggered=False,
                 reminder_days=0, last_repeat_reminder_date=None,
                 repeat_mode="None", repeat_interval_hours=None, repeat_interval_days=0,
                 next_occurrence=None, last_daily_reminder_time=None):
        self.date_time = date_time  # original scheduled time
        self.text = text
        self.sticky = sticky
        self.uid = uid or str(uuid.uuid4())
        self.last_ext_reminder = last_ext_reminder
        self.pre_final_triggered = pre_final_triggered
        self.final_reminder_triggered = final_reminder_triggered
        self.reminder_days = reminder_days  # for non-repeating daily reminders
        self.last_repeat_reminder_date = last_repeat_reminder_date  # for non-repeating daily reminders
        # New repeat fields:
        self.repeat_mode = repeat_mode  # "None", "Daily", "Weekly", "Monthly", "Yearly", "Custom"
        self.repeat_interval_hours = repeat_interval_hours  # for Custom mode (hours)
        self.repeat_interval_days = repeat_interval_days    # for Custom mode (days)
        # For repeating notes, next_occurrence is the upcoming occurrence (initially equals date_time)
        self.next_occurrence = next_occurrence if next_occurrence else date_time
        self.last_daily_reminder_time = last_daily_reminder_time  # for dynamic reminders on occurrence day

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
            'last_daily_reminder_time': self.last_daily_reminder_time.isoformat() if self.last_daily_reminder_time else None
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
        return cls(dt, text, sticky, uid, lr, pft, frt, r_days, last_repeat,
                   repeat_mode, repeat_interval_hours, repeat_interval_days,
                   next_occurrence, last_daily)

# -------------------------------
# StickyNoteWindow (unchanged)
# -------------------------------
class StickyNoteWindow(QWidget):
    closed = pyqtSignal(object)
    def __init__(self, note):
        super().__init__(None)
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

# -------------------------------
# ReminderDialog (unchanged)
# -------------------------------
class ReminderDialog(QDialog):
    def __init__(self, note, reminder_type):
        super().__init__()
        self.setWindowTitle("Reminder")
        layout = QVBoxLayout()
        if reminder_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.next_occurrence.strftime('%H:%M')}"
        elif reminder_type == "pre-final":
            msg = (
                f"Pre-Final Reminder (10 min before):\n{note.text}\n"
                f"Time: {(note.next_occurrence - datetime.timedelta(minutes=10)).strftime('%H:%M')}"
            )
        else:
            msg = f"Reminder:\n{note.text}"
        layout.addWidget(QLabel(msg))
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self.accept)
        layout.addWidget(dismiss)
        self.setLayout(layout)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

# -------------------------------
# MainWindow with Repeating/Reminding Refactor
# -------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RemindMeFy")
        self.notes = []
        self.load_notes()

        self.settings = {
            "startup": False,
            "days_earlier": 2,
            "ext_reminder_interval_hours": 4
        }
        self.load_settings()

        self.current_note_uid = None
        self.sorting_enabled = False
        self.archive_mode = False
        self.displayed_notes = []
        self.sticky_windows = {}
        self.preview_sticky_window = None

        self.init_ui()
        self.init_tray_icon()
        self.init_timer(10000)

    # ---------------------------
    # Dynamic (occurrence-day) Reminder Frequency
    # ---------------------------
    def get_dynamic_reminder(self, note):
        now = datetime.datetime.now()
        target = note.next_occurrence
        remaining = target - now
        # Set dynamic intervals:
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
        # Do not schedule past pre-final (10 min before target)
        pre_final = target - datetime.timedelta(minutes=10)
        if next_time > pre_final:
            return pre_final
        return next_time

    # ---------------------------
    # Compute Next Occurrence for Repeating Notes
    # ---------------------------
    def compute_next_occurrence(self, note):
        target = note.next_occurrence
        if note.repeat_mode == "Daily":
            return target + datetime.timedelta(days=1)
        elif note.repeat_mode == "Weekly":
            return target + datetime.timedelta(weeks=1)
        elif note.repeat_mode == "Monthly":
            return target + datetime.timedelta(days=30)  # approximation
        elif note.repeat_mode == "Yearly":
            return target + datetime.timedelta(days=365)
        elif note.repeat_mode == "Custom":
            # Add custom days and hours
            days = note.repeat_interval_days if note.repeat_interval_days else 0
            hours = note.repeat_interval_hours if note.repeat_interval_hours else 0
            return target + datetime.timedelta(days=days, hours=hours)
        else:
            return target

    # ---------------------------
    # Compute Next Reminder (for upcoming occurrence)
    # ---------------------------
    def compute_next_reminder(self, note):
        now = datetime.datetime.now()
        target = note.next_occurrence
        threshold = datetime.timedelta(minutes=10)
        pre_final_time = target - threshold
        if now < target:
            if note.repeat_mode != "None" and now.date() == target.date():
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

    # ---------------------------
    # Check Reminders and Update Occurrence for Repeating Notes
    # ---------------------------
    def check_reminders(self):
        now = datetime.datetime.now()
        for note in self.notes:
            # For repeating notes: if the current occurrence has passed, update it.
            if note.repeat_mode != "None" and now >= note.next_occurrence:
                note.next_occurrence = self.compute_next_occurrence(note)
                note.last_daily_reminder_time = None
                note.pre_final_triggered = False
                note.final_reminder_triggered = False
                note.last_ext_reminder = None
                note.last_repeat_reminder_date = None

            nxt, rtype, _ = self.compute_next_reminder(note)
            if nxt and now >= nxt:
                if rtype == "pre-final" and not note.pre_final_triggered:
                    self.show_reminder(note, "pre-final")
                    note.pre_final_triggered = True
                elif rtype == "ext":
                    if note.repeat_mode != "None" and now.date() == note.next_occurrence.date():
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

    # ---------------------------
    # Update Notes List (show next reminder and repeat info)
    # ---------------------------
    def update_notes_list(self):
        self.notes_list.clear()
        now = datetime.datetime.now()
        filtered = []
        for note in self.notes:
            # For nonrepeating, daily window end is note.date_time + (reminder_days-1) days
            if note.repeat_mode == "None":
                if note.reminder_days > 0:
                    window_end = note.date_time + datetime.timedelta(days=note.reminder_days - 1)
                else:
                    window_end = note.date_time
            else:
                window_end = note.next_occurrence  # current occurrence is active
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
            now = datetime.datetime.now()
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
            item_text = f"{occ_str} - {note.text} (Mode: {note.repeat_mode}"
            if note.repeat_mode == "Custom":
                item_text += f" {note.repeat_interval_days}d/{note.repeat_interval_hours}h"
            item_text += f"; {info})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, note.uid)
            self.notes_list.addItem(item)

    # ---------------------------
    # Toggle Sorting and Archive
    # ---------------------------
    def toggle_sorting(self):
        self.sorting_enabled = not self.sorting_enabled
        if self.sorting_enabled:
            self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
            self.sort_button.setToolTip("Sorting is ON (click to disable)")
        else:
            self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
            self.sort_button.setToolTip("Sorting is OFF (click to enable)")
        self.update_notes_list()

    def toggle_archive(self):
        self.archive_mode = not self.archive_mode
        if self.archive_mode:
            self.archive_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
            self.archive_button.setToolTip("Archived events are shown (click to hide)")
        else:
            self.archive_button.setIcon(self.style().standardIcon(QStyle.SP_DirHomeIcon))
            self.archive_button.setToolTip("Archived events are hidden (click to show)")
        self.update_notes_list()

    # ---------------------------
    # Tray Icon and Utility
    # ---------------------------
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

    def init_timer(self, interval_ms):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(interval_ms)

    # ---------------------------
    # Sticky Logic (unchanged)
    # ---------------------------
    def on_sticky_checkbox_toggled(self, checked):
        if checked:
            if self.current_note_uid:
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
                if self.preview_sticky_window is None:
                    preview_note = Note(datetime.datetime.now(), self.note_text.toPlainText(), sticky=True)
                    self.preview_sticky_window = StickyNoteWindow(preview_note)
                    self.preview_sticky_window.closed.connect(self.on_sticky_window_closed)
                    self.preview_sticky_window.show()
        else:
            if self.current_note_uid:
                note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
                if note and note.uid in self.sticky_windows:
                    self.sticky_windows[note.uid].close()
                    del self.sticky_windows[note.uid]
            else:
                if self.preview_sticky_window:
                    self.preview_sticky_window.close()
                    self.preview_sticky_window = None

    def on_sticky_window_closed(self, note):
        self.sticky_checkbox.blockSignals(True)
        self.sticky_checkbox.setChecked(False)
        self.sticky_checkbox.blockSignals(False)
        if note.uid in self.sticky_windows:
            del self.sticky_windows[note.uid]
        if self.preview_sticky_window and self.preview_sticky_window.note.uid == note.uid:
            self.preview_sticky_window = None

    # ---------------------------
    # CRUD Operations
    # ---------------------------
    def add_note(self):
        dt = datetime.datetime.combine(self.date_edit.date().toPyDate(), self.time_edit.time().toPyTime())
        text = self.note_text.toPlainText().strip()
        sticky = self.sticky_checkbox.isChecked()
        r_days = self.days_reminder_spinbox.value()
        repeat_mode = self.repeat_mode_combo.currentText() if hasattr(self, "repeat_mode_combo") else "None"
        # For custom mode, get both days and hours
        if repeat_mode == "Custom":
            custom_days = self.repeat_custom_days_spinbox.value()
            custom_hours = self.repeat_custom_hours_spinbox.value()
        else:
            custom_days = 0
            custom_hours = None
        if text:
            note = Note(dt, text, sticky=sticky, reminder_days=r_days,
                        repeat_mode=repeat_mode, repeat_interval_hours=custom_hours,
                        repeat_interval_days=custom_days)
            note.next_occurrence = dt
            self.notes.append(note)
            self.save_notes()
            self.update_notes_list()
            self.note_text.clear()
            self.clear_selection()
            if sticky:
                win = StickyNoteWindow(note)
                win.closed.connect(self.on_sticky_window_closed)
                win.show()
                self.sticky_windows[note.uid] = win
            if self.preview_sticky_window:
                self.preview_sticky_window.close()
                self.preview_sticky_window = None

    def update_note(self):
        if self.current_note_uid:
            dt = datetime.datetime.combine(self.date_edit.date().toPyDate(), self.time_edit.time().toPyTime())
            text = self.note_text.toPlainText().strip()
            sticky = self.sticky_checkbox.isChecked()
            r_days = self.days_reminder_spinbox.value()
            repeat_mode = self.repeat_mode_combo.currentText() if hasattr(self, "repeat_mode_combo") else "None"
            if repeat_mode == "Custom":
                custom_days = self.repeat_custom_days_spinbox.value()
                custom_hours = self.repeat_custom_hours_spinbox.value()
            else:
                custom_days = 0
                custom_hours = None
            if text:
                note = next((n for n in self.notes if n.uid == self.current_note_uid), None)
                if not note:
                    return
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
                note.last_repeat_reminder_date = None
                note.last_daily_reminder_time = None
                note.next_occurrence = dt
                self.save_notes()
                self.update_notes_list()
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
            self.save_notes()
            self.update_notes_list()
            self.clear_selection()

    def clear_selection(self):
        self.notes_list.clearSelection()
        self.current_note_uid = None
        self.note_text.clear()
        self.date_edit.setDate(datetime.date.today())
        self.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
        self.days_reminder_spinbox.setValue(0)
        self.next_reminder_label.setText("N/A")
        self.pre_final_label.setText("")
        self.reminder_info_label.setText("Reminder Info: N/A")
        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.sticky_checkbox.blockSignals(True)
        self.sticky_checkbox.setChecked(False)
        self.sticky_checkbox.blockSignals(False)
        if self.preview_sticky_window:
            self.preview_sticky_window.close()
            self.preview_sticky_window = None

    def load_note_details(self, item):
        uid = item.data(Qt.UserRole)
        self.current_note_uid = uid
        note = next((n for n in self.notes if n.uid == uid), None)
        if not note:
            return
        self.date_edit.setDate(note.date_time.date())
        self.time_edit.setTime(QTime(note.date_time.hour, note.date_time.minute))
        self.note_text.setText(note.text)
        self.days_reminder_spinbox.setValue(note.reminder_days)
        # Set repeat mode UI:
        self.repeat_mode_combo.setCurrentText(note.repeat_mode)
        if note.repeat_mode == "Custom":
            self.repeat_custom_days_spinbox.setValue(note.repeat_interval_days)
            self.repeat_custom_hours_spinbox.setValue(note.repeat_interval_hours if note.repeat_interval_hours is not None else 0)
        else:
            self.repeat_custom_days_spinbox.setValue(0)
            self.repeat_custom_hours_spinbox.setValue(0)
        self.update_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.sticky_checkbox.blockSignals(True)
        self.sticky_checkbox.setChecked(note.sticky)
        self.sticky_checkbox.blockSignals(False)

        now = datetime.datetime.now()
        if note.date_time > now:
            nxt, rtype, _ = self.compute_next_reminder(note)
            nxt_str = nxt.strftime("%Y-%m-%d %H:%M") if nxt else "None"
            self.next_reminder_label.setText(f"Next Reminder: {nxt_str}")
            self.pre_final_label.setText("")
        else:
            if note.repeat_mode != "None":
                dyn = self.get_dynamic_reminder(note)
                nxt_str = dyn.strftime("%Y-%m-%d %H:%M") if dyn else "None"
                self.next_reminder_label.setText(f"Next Daily Reminder: {nxt_str}")
            else:
                self.next_reminder_label.setText("Event Passed")
                self.next_reminder_label.setStyleSheet("color: red;")
            self.pre_final_label.setText(f"Occurrence: {note.next_occurrence.strftime('%Y-%m-%d %H:%M')}")
        if note.repeat_mode != "None":
            info = f"Repeat: {note.repeat_mode}"
            if note.repeat_mode == "Custom":
                info += f" ({note.repeat_interval_days}d/{note.repeat_interval_hours}h)"
        else:
            info = "Non-repeating"
        self.reminder_info_label.setText(f"Reminder Info: {info}")

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

    # ---------------------------
    # Reminders: Check and Trigger
    # ---------------------------
    def check_reminders(self):
        now = datetime.datetime.now()
        for note in self.notes:
            if note.repeat_mode != "None" and now >= note.next_occurrence:
                note.next_occurrence = self.compute_next_occurrence(note)
                note.last_daily_reminder_time = None
                note.pre_final_triggered = False
                note.final_reminder_triggered = False
                note.last_ext_reminder = None
                note.last_repeat_reminder_date = None

            nxt, rtype, _ = self.compute_next_reminder(note)
            if nxt and now >= nxt:
                if rtype == "pre-final" and not note.pre_final_triggered:
                    self.show_reminder(note, "pre-final")
                    note.pre_final_triggered = True
                elif rtype == "ext":
                    if note.repeat_mode != "None" and now.date() == note.next_occurrence.date():
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

    # ---------------------------
    # Compute Next Reminder for Current Occurrence
    # ---------------------------
    def compute_next_reminder(self, note):
        now = datetime.datetime.now()
        target = note.next_occurrence
        threshold = datetime.timedelta(minutes=10)
        pre_final_time = target - threshold
        if now < target:
            if note.repeat_mode != "None" and now.date() == target.date():
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

    # ---------------------------
    # Compute Next Occurrence for Repeating Notes
    # ---------------------------
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

    # ---------------------------
    # Show Reminder
    # ---------------------------
    def show_reminder(self, note, r_type):
        if r_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.next_occurrence.strftime('%H:%M')}"
        elif r_type == "ext":
            msg = f"Reminder:\n{note.text}\nOccurrence: {note.next_occurrence.strftime('%Y-%m-%d %H:%M')}"
        elif r_type == "pre-final":
            msg = (
                f"Pre-Final Reminder:\n{note.text}\n"
                f"Time: {(note.next_occurrence - datetime.timedelta(minutes=10)).strftime('%H:%M')}"
            )
        else:
            msg = f"Reminder:\n{note.text}"
        self.tray_icon.showMessage("RemindMeFy Reminder", msg, QSystemTrayIcon.Information, 10000)
        if not self.isVisible():
            self.show_normal()
        dlg = ReminderDialog(note, r_type)
        dlg.exec_()

    # ---------------------------
    # Tray and Timer
    # ---------------------------
    def show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

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

    def init_timer(self, interval_ms):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(interval_ms)

    # ---------------------------
    # Repeat Mode UI Setup
    # ---------------------------
    def setup_repeat_ui(self, parent_layout):
        hbox = QHBoxLayout()
        label = QLabel("Repeat Mode:")
        hbox.addWidget(label)
        self.repeat_mode_combo = QComboBox()
        self.repeat_mode_combo.addItems(["None", "Daily", "Weekly", "Monthly", "Yearly", "Custom"])
        hbox.addWidget(self.repeat_mode_combo)
        # For Custom mode, add two spin boxes: days and hours.
        self.repeat_custom_days_spinbox = QSpinBox()
        self.repeat_custom_days_spinbox.setRange(0, 30)
        self.repeat_custom_days_spinbox.setValue(0)
        self.repeat_custom_days_spinbox.setEnabled(False)
        hbox.addWidget(QLabel("Custom Interval (days):"))
        hbox.addWidget(self.repeat_custom_days_spinbox)
        self.repeat_custom_hours_spinbox = QSpinBox()
        self.repeat_custom_hours_spinbox.setRange(0, 23)
        self.repeat_custom_hours_spinbox.setValue(0)
        self.repeat_custom_hours_spinbox.setEnabled(False)
        hbox.addWidget(QLabel("Custom Interval (hrs):"))
        hbox.addWidget(self.repeat_custom_hours_spinbox)
        self.repeat_mode_combo.currentTextChanged.connect(self.on_repeat_mode_changed)
        parent_layout.addLayout(hbox)

    def on_repeat_mode_changed(self, text):
        if text == "Custom":
            self.repeat_custom_days_spinbox.setEnabled(True)
            self.repeat_custom_hours_spinbox.setEnabled(True)
        else:
            self.repeat_custom_days_spinbox.setEnabled(False)
            self.repeat_custom_hours_spinbox.setEnabled(False)

    # ---------------------------
    # Modify init_ui to add Repeat Mode UI.
    # ---------------------------
    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
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

        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Days to Remind:"))
        self.days_reminder_spinbox = QSpinBox()
        self.days_reminder_spinbox.setRange(0,30)
        days_layout.addWidget(self.days_reminder_spinbox)
        notes_layout.addLayout(days_layout)

        self.setup_repeat_ui(notes_layout)

        notes_layout.addWidget(QLabel("Enter Note:"))
        self.note_text = QTextEdit()
        notes_layout.addWidget(self.note_text)

        self.sticky_checkbox = QCheckBox("Sticky Note")
        self.sticky_checkbox.toggled.connect(self.on_sticky_checkbox_toggled)
        notes_layout.addWidget(self.sticky_checkbox)

        self.next_reminder_label = QLabel("N/A")
        notes_layout.addWidget(self.next_reminder_label)
        self.pre_final_label = QLabel("")
        notes_layout.addWidget(self.pre_final_label)
        self.reminder_info_label = QLabel("Reminder Info: N/A")
        notes_layout.addWidget(self.reminder_info_label)

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

        button_layout = QHBoxLayout()
        self.sort_button = QToolButton()
        self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self.sort_button.setToolTip("Toggle sorting")
        self.sort_button.clicked.connect(self.toggle_sorting)
        button_layout.addWidget(self.sort_button)
        self.archive_button = QToolButton()
        self.archive_button.setIcon(self.style().standardIcon(QStyle.SP_DirHomeIcon))
        self.archive_button.setToolTip("Show archived events")
        self.archive_button.clicked.connect(self.toggle_archive)
        button_layout.addWidget(self.archive_button)
        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_button.setToolTip("Refresh notes")
        self.refresh_button.clicked.connect(self.update_notes_list)
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        notes_layout.addLayout(button_layout)

        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self.load_note_details)
        notes_layout.addWidget(self.notes_list)

        self.notes_tab.setLayout(notes_layout)
        self.tabs.addTab(self.notes_tab, "Notes")

        self.settings_tab = QWidget()
        st_layout = QVBoxLayout()
        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(self.settings.get("startup", False))
        st_layout.addWidget(self.startup_checkbox)
        desc = QLabel("If checked, RemindMeFy will automatically start when Windows boots.")
        desc.setStyleSheet("font-size: 10pt; color: gray;")
        st_layout.addWidget(desc)
        st_layout.addWidget(QLabel("Days earlier to start reminding:"))
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(0,30)
        self.days_spinbox.setValue(self.settings.get("days_earlier",2))
        st_layout.addWidget(self.days_spinbox)
        st_layout.addWidget(QLabel("Ext Reminder Frequency (hours):"))
        self.ext_interval_spinbox = QSpinBox()
        self.ext_interval_spinbox.setRange(1,24)
        self.ext_interval_spinbox.setValue(self.settings.get("ext_reminder_interval_hours",4))
        st_layout.addWidget(self.ext_interval_spinbox)
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.clicked.connect(self.save_settings)
        st_layout.addWidget(self.save_settings_button)
        self.settings_tab.setLayout(st_layout)
        self.tabs.addTab(self.settings_tab, "Settings")

        self.update_notes_list()

    # ---------------------------
    # (The remaining methods – tray, timer, CRUD, load/save, check_reminders, compute_next_reminder, compute_next_occurrence, show_reminder – remain unchanged)
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

    def init_timer(self, interval_ms):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(interval_ms)

    def check_reminders(self):
        now = datetime.datetime.now()
        for note in self.notes:
            if note.repeat_mode != "None" and now >= note.next_occurrence:
                note.next_occurrence = self.compute_next_occurrence(note)
                note.last_daily_reminder_time = None
                note.pre_final_triggered = False
                note.final_reminder_triggered = False
                note.last_ext_reminder = None
                note.last_repeat_reminder_date = None

            nxt, rtype, _ = self.compute_next_reminder(note)
            if nxt and now >= nxt:
                if rtype == "pre-final" and not note.pre_final_triggered:
                    self.show_reminder(note, "pre-final")
                    note.pre_final_triggered = True
                elif rtype == "ext":
                    if note.repeat_mode != "None" and now.date() == note.next_occurrence.date():
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

    def compute_next_reminder(self, note):
        now = datetime.datetime.now()
        target = note.next_occurrence
        threshold = datetime.timedelta(minutes=10)
        pre_final_time = target - threshold
        if now < target:
            if note.repeat_mode != "None" and now.date() == target.date():
                dyn = self.get_dynamic_reminder(note)
                if dyn >= pre_final_time:
                    return (pre_final_time, "pre-final", pre_final_time)
                return (dyn, "ext", pre_final_time)
            else:
                ext_interval = datetime.timedelta(hours=self.settings.get("ext_reminder_interval_hours",4))
                days_earlier = self.settings.get("days_earlier",2)
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

    def show_reminder(self, note, r_type):
        if r_type == "final":
            msg = f"Final Reminder:\n{note.text}\nTime: {note.next_occurrence.strftime('%H:%M')}"
        elif r_type == "ext":
            msg = f"Reminder:\n{note.text}\nOccurrence: {note.next_occurrence.strftime('%Y-%m-%d %H:%M')}"
        elif r_type == "pre-final":
            msg = (
                f"Pre-Final Reminder:\n{note.text}\n"
                f"Time: {(note.next_occurrence - datetime.timedelta(minutes=10)).strftime('%H:%M')}"
            )
        else:
            msg = f"Reminder:\n{note.text}"
        self.tray_icon.showMessage("RemindMeFy Reminder", msg, QSystemTrayIcon.Information, 10000)
        if not self.isVisible():
            self.show_normal()
        dlg = ReminderDialog(note, r_type)
        dlg.exec_()

if __name__=="__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
