import sys
import asyncio
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop
from src.ui.main_window import TelegramApp as MainWindow


class AsyncQApplication(QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._async_loop = QEventLoop()

    def exec_async(self, coro):
        self._async_loop.run_until_complete(coro)


def main():
    app = AsyncQApplication(sys.argv)
    app.setApplicationName("Telegram Staff Control")
    app.setOrganizationName("StaffApp")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
