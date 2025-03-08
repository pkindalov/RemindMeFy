import datetime
import json
import os
from math import ceil
import pytest

from RemindMeFy import MainWindow, Note  # Adjust module name if needed

# Fake datetime class for overriding now() in tests.
class FakeDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fake_now

@pytest.fixture
def main_window(monkeypatch, tmp_path):
    # Create an instance of MainWindow and fix the app start time.
    mw = MainWindow()
    mw.app_start_time = datetime.datetime(2025, 3, 8, 8, 0)  # Fixed start time: March 8, 2025, 08:00
    # Monkey-patch datetime.datetime with our FakeDateTime.
    monkeypatch.setattr(datetime, "datetime", FakeDateTime)
    # Use a temporary file for notes (if your app supports overriding note file path, adjust here).
    # For now, we assume notes.json is used; we delete it if present.
    tmp_notes = tmp_path / "notes.json"
    if tmp_notes.exists():
        tmp_notes.unlink()
    return mw

# -----------------------
# Edge Case Tests
# -----------------------

def test_exactly_10_minutes(main_window):
    """
    If the event is exactly 10 minutes away, it should be considered within threshold (final).
    """
    # Set simulated current time.
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 9, 0)
    target = datetime.datetime(2025, 3, 8, 9, 10)  # exactly 10 minutes away
    note = Note(target, "Edge: Exactly 10 minutes away")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # Expect final reminder.
    assert r_type == "final"
    assert next_rem == target

def test_ext_reminder_boundary(main_window):
    """
    Test when the computed ext reminder exactly equals the event time.
    For example, if app start is 08:00, ext interval is 4 hours,
    and the event is at 20:00. Then at 2025-03-08 19:59, the next computed reminder would be 20:00.
    """
    # Simulate now just before the event.
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 19, 59)
    target = datetime.datetime(2025, 3, 8, 20, 0)
    note = Note(target, "Edge: Reminder boundary")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # Since computed ext would be 20:00, we should get final reminder.
    assert r_type == "final"
    assert next_rem == target

def test_event_on_boundary_of_window(main_window):
    """
    If an event is exactly on the boundary of the "days earlier" window,
    then ext reminders should be active.
    For example, with days_earlier = 2, if now is March 8, 09:00 and event is March 10, 09:00,
    then the difference is exactly 2 days. In our logic, we consider ext reminders to be active if event - now <= days_earlier.
    """
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 9, 0)
    target = datetime.datetime(2025, 3, 10, 9, 0)
    note = Note(target, "Event on window boundary")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # With default days_earlier = 2 days, the event is exactly 2 days away so ext reminders should be active.
    # The computed next reminder will be based on app_start_time (08:00) and ext interval (4 hours).
    # At 09:00, (09:00-08:00)=1 hour so next ext is baseline + ceil(1/4)*4 = 08:00 + 4 = 12:00.
    expected = datetime.datetime(2025, 3, 8, 12, 0)
    assert r_type == "ext"
    assert next_rem == expected

# -----------------------
# Persistence Tests
# -----------------------

def test_save_and_load_notes(tmp_path):
    """
    Test that notes are saved to disk and can be reloaded.
    """
    # Create a temporary notes file.
    notes_file = tmp_path / "notes.json"
    # Create a note.
    note = Note(datetime.datetime(2025, 3, 8, 10, 0), "Persistence Test Note")
    notes = [note]
    # Save notes.
    with open(notes_file, "w") as f:
        data = [n.to_dict() for n in notes]
        json.dump(data, f)
    # Load notes.
    with open(notes_file, "r") as f:
        loaded_data = json.load(f)
    loaded_notes = [Note.from_dict(d) for d in loaded_data]
    assert len(loaded_notes) == 1
    assert loaded_notes[0].text == "Persistence Test Note"
    assert loaded_notes[0].date_time == datetime.datetime(2025, 3, 8, 10, 0)

# -----------------------
# Settings Impact Tests
# -----------------------

def test_ext_reminder_with_different_settings(main_window):
    """
    Change settings to different ext reminder frequency and days earlier,
    then verify that the computed next reminder time adjusts accordingly.
    """
    # Set the settings.
    main_window.settings["ext_reminder_interval_hours"] = 2  # every 2 hours
    main_window.settings["days_earlier"] = 1  # 1 day window
    # Simulate now as 2025-03-08 09:00.
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 9, 0)
    # Set an event 20 hours from now (i.e. 2025-03-09 05:00).
    target = datetime.datetime(2025, 3, 9, 5, 0)
    note = Note(target, "Settings Impact Test")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # With app_start_time = 2025-03-08 08:00, ext interval = 2 hours, and now = 09:00,
    # the next ext reminder should be computed as 08:00 + n*2 hours > 09:00.
    # n = ceil((09:00-08:00)/2) = ceil(1/2)=1, so next_ext = 08:00+2 = 10:00.
    expected_ext = datetime.datetime(2025, 3, 8, 10, 0)
    # As long as expected_ext is before the target, it should be returned with type "ext".
    assert r_type == "ext"
    assert next_rem == expected_ext
