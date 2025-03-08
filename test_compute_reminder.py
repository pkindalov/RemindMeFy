import datetime
from math import ceil
import pytest

# Import MainWindow and Note from your app module (adjust the module name as needed).
from RemindMeFy import MainWindow, Note

# A fake datetime class to override now().
class FakeDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fake_now

@pytest.fixture
def main_window(monkeypatch):
    # Create an instance of MainWindow
    mw = MainWindow()
    # Set a fixed app_start_time for reproducibility.
    mw.app_start_time = datetime.datetime(2025, 3, 8, 8, 0)  # March 8, 2025 at 08:00
    # Monkey-patch datetime.datetime with FakeDateTime.
    monkeypatch.setattr(datetime, "datetime", FakeDateTime)
    return mw

def test_final_reminder_within_threshold(main_window):
    # Simulate now = 2025-03-08 09:00; event is 2025-03-08 09:05 (within 10 minutes)
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 9, 0)
    target = datetime.datetime(2025, 3, 8, 9, 5)
    note = Note(target, "Event near threshold")
    next_rem, r_type = main_window.compute_next_reminder(note)
    assert r_type == "final"
    assert next_rem == target

def test_ext_reminder_calculation(main_window):
    # Simulate now = 2025-03-08 09:00; event is 2025-03-08 18:00 (9 hours away, within 2 days)
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 9, 0)
    target = datetime.datetime(2025, 3, 8, 18, 0)
    note = Note(target, "Future event same day")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # With app_start_time = 08:00 and ext interval = 4 hours, the next ext reminder should be:
    # 08:00 + 1×4 = 12:00, since 12:00 < 18:00.
    expected_ext = datetime.datetime(2025, 3, 8, 12, 0)
    assert r_type == "ext"
    assert next_rem == expected_ext

def test_ext_reminder_becomes_final(main_window):
    # Simulate now = 2025-03-08 18:00; event is 2025-03-08 18:30.
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 18, 0)
    target = datetime.datetime(2025, 3, 8, 18, 30)
    note = Note(target, "Event soon")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # With app_start_time = 08:00, now - baseline = 10 hours; with ext_interval = 4 hours:
    # n = ceil(10/4) = 3, so next_ext = 08:00 + 12 hours = 20:00, which is after the event.
    # Therefore, the function should return final reminder at the event time.
    assert r_type == "final"
    assert next_rem == target

def test_event_outside_window(main_window):
    # Simulate now = 2025-03-08 09:00; event is 2025-03-11 09:00, which is 3 days away.
    FakeDateTime.fake_now = datetime.datetime(2025, 3, 8, 9, 0)
    target = datetime.datetime(2025, 3, 11, 9, 0)
    note = Note(target, "Event too far in future")
    next_rem, r_type = main_window.compute_next_reminder(note)
    # With days_earlier = 2 days (48 hours), and event is 72 hours away, it should return (None, None).
    assert next_rem is None
    assert r_type is None
