import datetime
import json
import os
import pytest
from PyQt5.QtCore import Qt
from RemindMeFy import MainWindow  # Adjust import if necessary


@pytest.fixture
def main_window(qtbot, tmp_path):
    """
    Create a MainWindow instance, set a temporary file for persistence,
    and add it to qtbot.
    """
    # Optionally, override the note file location in your MainWindow if you want to use a temporary file.
    # For simplicity, we'll assume the app uses 'notes.json' in the current directory.
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()
    # Ensure a clean state by removing any existing notes file.
    notes_file = tmp_path / "notes.json"
    if notes_file.exists():
        notes_file.unlink()
    return mw


def test_edit_note_gui(main_window, qtbot, tmp_path):
    """
    Test that editing a note updates the note list and saved data.
    """
    # Add a note first.
    future_date = datetime.date.today() + datetime.timedelta(days=1)
    main_window.date_edit.setDate(future_date)
    main_window.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
    original_text = "Original Note"
    main_window.note_text.setPlainText(original_text)
    qtbot.mouseClick(main_window.add_button, Qt.LeftButton)

    # Select the newly added note.
    last_index = main_window.notes_list.count() - 1
    item = main_window.notes_list.item(last_index)
    qtbot.mouseClick(main_window.notes_list.viewport(), Qt.LeftButton, pos=item.pos())

    # Edit the note text.
    new_text = "Edited Note"
    main_window.note_text.setPlainText(new_text)
    qtbot.mouseClick(main_window.update_button, Qt.LeftButton)

    # Check that the note list shows the updated note.
    updated_item = main_window.notes_list.item(last_index)
    assert new_text in updated_item.text()

    # Optionally, check that the note is saved correctly.
    with open("notes.json", "r") as f:
        data = json.load(f)
    assert any(new_text in note["text"] for note in data)


def test_delete_note_gui(main_window, qtbot, tmp_path):
    """
    Test that deleting a note removes it from the note list and from saved data.
    """
    # Add a note.
    future_date = datetime.date.today() + datetime.timedelta(days=1)
    main_window.date_edit.setDate(future_date)
    main_window.time_edit.setTime(datetime.datetime.now().time().replace(second=0, microsecond=0))
    test_text = "Note to Delete"
    main_window.note_text.setPlainText(test_text)
    qtbot.mouseClick(main_window.add_button, Qt.LeftButton)

    initial_count = main_window.notes_list.count()
    assert initial_count > 0

    # Select the note.
    last_index = initial_count - 1
    item = main_window.notes_list.item(last_index)
    qtbot.mouseClick(main_window.notes_list.viewport(), Qt.LeftButton, pos=item.pos())

    # Click the Delete Note button.
    qtbot.mouseClick(main_window.delete_button, Qt.LeftButton)

    # Check that the note list count decreased.
    assert main_window.notes_list.count() == initial_count - 1

    # Optionally, check that the note is removed from the saved file.
    with open("notes.json", "r") as f:
        data = json.load(f)
    assert not any(test_text in note["text"] for note in data)
