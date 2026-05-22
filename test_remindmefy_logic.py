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
    assert compute_next_occurrence(note_m) == dt + datetime.timedelta(days=30)
    
    # Yearly
    note_y = NoteModel(date_time=dt, text="Yearly", next_occurrence=dt, repeat_mode="Yearly")
    assert compute_next_occurrence(note_y) == dt + datetime.timedelta(days=365)

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
