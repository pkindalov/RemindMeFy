# RemindMeFy

**RemindMeFy** is a modern, lightweight, and intuitive reminder application designed to keep your life organized. Built with a focus on simplicity and aesthetics, it features a sleek `customtkinter` interface that stays out of your way until you need it.

---

## Features

- **Modern Interface:** A clean, card-based UI with full support for **Light**, **Dark** themes.
- **Smart Recurrence:** Support for Daily, Weekly, Monthly, Yearly, and Custom repeat modes.
- **Dynamic Reminders:** Intelligent notification system that increases frequency as your event approaches.
- **Sticky Notes:** Pin important reminders to your desktop as floating sticky notes.
- **Visual Pickers:** Easy-to-use custom Calendar and Clock pickers for precise scheduling.
- **Tray Integration:** Runs quietly in the system tray with background monitoring.
- **Windows Auto-launch:** Optional startup integration to ensure you never miss a reminder.
- **Archive Management:** Keep your dashboard clean by archiving past events automatically.

---

## Technology Stack

- **Python 3.12+**
- **GUI:** [customtkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Data Validation:** [Pydantic V2](https://docs.pydantic.dev/)
- **Tray Icon:** [pystray](https://github.com/moses-palmer/pystray)
- **Persistence:** Atomic JSON storage

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- `pip` package manager

### Installation

1. Clone the repository:
2. Install dependencies:
   ```bash
   pip install customtkinter pystray pydantic pillow
   ```

3. Run the application:
   ```bash
   python RemindMeFy.py
   ```

---

## Testing

We use `pytest` for ensuring the reliability of the core reminder logic.

To run the tests:
```bash
pytest test_remindmefy_logic.py
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---


RemindMeFy isn't just a tool; it's a digital companion designed to reduce cognitive load. Whether it's a quick task or a yearly anniversary, RemindMeFy handles the "when" so you can focus on the "what."

---

