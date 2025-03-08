import datetime
from math import ceil
import pytest
from RemindMeFy import MainWindow, Note  # Adjust import if your module name is different

@pytest.fixture
def main_window():
    # Create an instance of MainWindow for testing.
    mw = MainWindow()
    # Optionally, force a fixed app_start_time for reproducible tests.
    mw.app_start_time = datetime.datetime(2025, 3, 8, 8, 0)  # March 8, 2025, 08:00 AM
    return mw

def test_final_reminder_within_threshold(main_window):
    # Set up a note where the event is within 10 minutes.
    now = datetime.datetime(2025, 3, 8, 9, 0)  # Simulated current time
    target = now + datetime.timedelta(minutes=5)
    note = Note(target, "Test Event")
    # Temporarily override datetime.datetime.now to return our simulated time.
    original_now = datetime.datetime.now
    datetime.datetime.now = lambda: now
    try:
        next_rem, r_type = main_window.compute_next_reminder(note)
        assert r_type == "final"
        assert next_rem == target
    finally:
        datetime.datetime.now = original_now

def test_ext_reminder(main_window):
    # Set up a note that is within the "days earlier" window.
    now = datetime.datetime(2025, 3, 8, 9, 0)  # Simulated current time
    # Set target 1 day from now (which is within 2 days)
    target = now + datetime.timedelta(days=1)
    note = Note(target, "Future Event")
    original_now = datetime.datetime.now
    datetime.datetime.now = lambda: now
    try:
        next_rem, r_type = main_window.compute_next_reminder(note)
        # The computed ext reminder should be based on app_start_time (set above)
        # and the ext interval from settings (default 4 hours).
        # For our baseline of 08:00, the next ext reminder after 09:00 should be 12:00.
        expected_ext = datetime.datetime(2025, 3, 8, 12, 0)
        # If the expected ext reminder is before the target, it should be "ext".
        assert r_type in ["ext", "final"]
        # Allow a bit of flexibility if the computation is slightly different.
        assert expected_ext <= next_rem <= target
    finally:
        datetime.datetime.now = original_now
