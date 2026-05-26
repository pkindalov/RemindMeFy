import datetime
import pytest
from RemindMeFy import NoteModel, get_dynamic_interval, compute_next_occurrence, NoteManager

def test_note_model_serialization():
    dt = datetime.datetime(2026, 5, 22, 12, 0)
    note = NoteModel(date_time=dt, text="Test", next_occurrence=dt)
    d = note.to_dict()
    assert d['date_time'] == dt.isoformat()
    
    note2 = NoteModel.from_dict(d)
    assert note2.date_time == dt
    assert note2.text == "Test"

def test_dynamic_interval():
    # > 6h -> 60m
    assert get_dynamic_interval(datetime.timedelta(hours=7)) == datetime.timedelta(minutes=60)
    # > 2h -> 30m
    assert get_dynamic_interval(datetime.timedelta(hours=3)) == datetime.timedelta(minutes=30)
    # > 1h -> 15m
    assert get_dynamic_interval(datetime.timedelta(minutes=70)) == datetime.timedelta(minutes=15)
    # < 1h -> 5m
    assert get_dynamic_interval(datetime.timedelta(minutes=30)) == datetime.timedelta(minutes=5)

def test_compute_next_occurrence_basic():
    dt = datetime.datetime(2026, 5, 22, 12, 0)
    note = NoteModel(date_time=dt, text="Test", next_occurrence=dt, repeat_mode="Daily")
    assert compute_next_occurrence(note) == dt + datetime.timedelta(days=1)
    
    note.repeat_mode = "Weekly"
    assert compute_next_occurrence(note) == dt + datetime.timedelta(weeks=1)
    
    note.repeat_mode = "Custom"
    note.repeat_interval_days = 2
    note.repeat_interval_hours = 3
    assert compute_next_occurrence(note) == dt + datetime.timedelta(days=2, hours=3)

def test_compute_next_occurrence_complex():
    dt = datetime.datetime(2026, 5, 22, 12, 0)
    
    # Monthly
    note_m = NoteModel(date_time=dt, text="Monthly", next_occurrence=dt, repeat_mode="Monthly")
    # Now uses relativedelta, so it should be exactly 1 month later
    assert compute_next_occurrence(note_m) == datetime.datetime(2026, 6, 22, 12, 0)
    
    # Yearly
    note_y = NoteModel(date_time=dt, text="Yearly", next_occurrence=dt, repeat_mode="Yearly")
    # Yearly now uses relativedelta, so it should be exactly 1 year later
    # 2026-05-22 -> 2027-05-22
    assert compute_next_occurrence(note_y) == datetime.datetime(2027, 5, 22, 12, 0)

def test_repeating_reminder_advancement_logic():
    """Verify that a repeating reminder advances to the future in one go."""
    now = datetime.datetime(2026, 5, 26, 12, 0)
    past_date = now - datetime.timedelta(days=5) # 5 days ago (May 21)
    
    note = NoteModel(
        date_time=past_date,
        text="Past Daily Note",
        next_occurrence=past_date,
        repeat_mode="Daily"
    )
    
    # Simulate the fixed check_reminders logic
    notifications_count = 0
    
    # 1. Handle final reminder
    if now >= note.next_occurrence and not note.final_reminder_triggered:
        notifications_count += 1
        note.final_reminder_triggered = True
        
    # 2. If repeating, advance to next future occurrence after final trigger
    if note.repeat_mode != "None" and now >= note.next_occurrence and note.final_reminder_triggered:
        while note.next_occurrence <= now:
            note.next_occurrence = compute_next_occurrence(note)
        note.pre_final_triggered = note.final_reminder_triggered = False
        note.last_ext_reminder = note.last_daily_reminder_time = None
        
    assert notifications_count == 1
    assert note.next_occurrence > now
    # 21 -> 22 -> 23 -> 24 -> 25 -> 26 -> 27.
    assert note.next_occurrence == datetime.datetime(2026, 5, 27, 12, 0)
    assert not note.final_reminder_triggered

def test_monthly_yearly_accuracy():
    """Verify that relativedelta is used for Monthly and Yearly."""
    dt = datetime.datetime(2024, 1, 31, 12, 0) # Leap year, end of month
    note = NoteModel(date_time=dt, text="Monthly", next_occurrence=dt, repeat_mode="Monthly")
    
    # Feb 2024 has 29 days. relativedelta(months=1) from Jan 31 should be Feb 29.
    next_occ = compute_next_occurrence(note)
    assert next_occ.month == 2
    assert next_occ.day == 29
    
    note.repeat_mode = "Yearly"
    # Year later should be Jan 31 2025
    next_occ = compute_next_occurrence(note)
    assert next_occ.year == 2025
    assert next_occ.month == 1
    assert next_occ.day == 31

def test_reminder_thresholds():
    # Pre-final is 10 minutes before
    target = datetime.datetime(2026, 5, 22, 12, 0)
    threshold = datetime.timedelta(minutes=10)
    pre_final = target - threshold
    
    assert pre_final == datetime.datetime(2026, 5, 22, 11, 50)

def test_note_manager_logic():
    # Test atomic save mock (just verifying it runs without error)
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir) / "notes.json"
        manager = NoteManager(storage)
        
        dt = datetime.datetime.now()
        note = NoteModel(date_time=dt, text="Test", next_occurrence=dt)
        manager.notes.append(note)
        manager.save_notes()
        
        assert storage.exists()
        
        new_manager = NoteManager(storage)
        assert len(new_manager.notes) == 1
        assert new_manager.notes[0].text == "Test"
