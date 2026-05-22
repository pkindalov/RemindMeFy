import datetime
import pytest
from RemindMeFy import NoteModel, get_dynamic_interval, compute_next_occurrence

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

def test_compute_next_occurrence():
    dt = datetime.datetime(2026, 5, 22, 12, 0)
    note = NoteModel(date_time=dt, text="Test", next_occurrence=dt, repeat_mode="Daily")
    next_occ = compute_next_occurrence(note)
    assert next_occ == dt + datetime.timedelta(days=1)
    
    note.repeat_mode = "Weekly"
    assert compute_next_occurrence(note) == dt + datetime.timedelta(weeks=1)
    
    note.repeat_mode = "Custom"
    note.repeat_interval_days = 2
    note.repeat_interval_hours = 3
    assert compute_next_occurrence(note) == dt + datetime.timedelta(days=2, hours=3)
