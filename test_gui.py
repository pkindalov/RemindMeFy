import datetime
import pytest
from PyQt5.QtCore import Qt
from RemindMeFy import MainWindow  # Adjust the import if your module is named differently

@pytest.fixture
def main_window(qtbot):
    # Create an instance of MainWindow for testing.
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()
    return mw

def test_add_note_gui(main_window, qtbot):
    """
    Simulate adding a note through the GUI and verify that the note appears in the note list.
    """
    # Set a future date for the note (e.g., tomorrow).
    future_date = datetime.date.today() + datetime.timedelta(days=1)
    main_window.date_edit.setDate(future_date)
    # Set the time to the current time (or any valid time).
    current_time = datetime.datetime.now().time().replace(second=0, microsecond=0)
    main_window.time_edit.setTime(current_time)
    # Enter note text.
    test_text = "GUI Test Note"
    main_window.note_text.setPlainText(test_text)
    # Simulate clicking the "Add Note" button.
    qtbot.mouseClick(main_window.add_button, Qt.LeftButton)
    # Verify that the note list now has at least one note.
    assert main_window.notes_list.count() > 0
    # Check that the last item in the list contains our test note text.
    last_item = main_window.notes_list.item(main_window.notes_list.count() - 1)
    assert test_text in last_item.text()

def test_event_passed_label_gui(main_window, qtbot):
    """
    Simulate adding a note for a past event and verify that the "Next Reminder" label displays "Event Passed" in red.
    """
    # Set a past date for the note (e.g., yesterday).
    past_date = datetime.date.today() - datetime.timedelta(days=1)
    main_window.date_edit.setDate(past_date)
    # Set the time (any time, since the date is in the past).
    main_window.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
    # Enter note text.
    test_text = "Past Event"
    main_window.note_text.setPlainText(test_text)
    # Click "Add Note".
    qtbot.mouseClick(main_window.add_button, Qt.LeftButton)
    # Select the newly added note.
    last_index = main_window.notes_list.count() - 1
    item = main_window.notes_list.item(last_index)
    qtbot.mouseClick(main_window.notes_list.viewport(), Qt.LeftButton, pos=item.pos())
    # Verify that the next reminder label displays "Event Passed".
    assert "Event Passed" in main_window.next_reminder_label.text()
    # Check that the style sheet indicates red text.
    assert "red" in main_window.next_reminder_label.styleSheet()
