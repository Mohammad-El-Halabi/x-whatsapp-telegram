import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        from src.ui.main_window import SMSApp
        app = SMSApp()
        app.mainloop()
    except Exception:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
        with open(log_path, "w") as f:
            traceback.print_exc(file=f)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Application Error",
                f"A critical error occurred.\n\n"
                f"Details have been saved to:\n{log_path}\n\n"
                f"Please send this file to support."
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
