import datetime
import pytest
from PyQt5.QtCore import Qt
from RemindMeFy import MainWindow  # Adjust according to your module name

@pytest.fixture
def main_window(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()
    return mw

def test_add_note_gui(main_window, qtbot):
    # Set a future date for the note.
    future_date = datetime.date.today() + datetime.timedelta(days=1)
    main_window.date_edit.setDate(future_date)
    main_window.time_edit.setTime(datetime.datetime.now().time())
    # Enter note text.
    main_window.note_text.setPlainText("GUI Test Note")
    # Simulate clicking the "Add Note" button.
    qtbot.mouseClick(main_window.add_button, Qt.LeftButton)
    # Check that a note was added to the list.
    assert main_window.notes_list.count() > 0
    last_item = main_window.notes_list.item(main_window.notes_list.count() - 1)
    assert "GUI Test Note" in last_item.text()
