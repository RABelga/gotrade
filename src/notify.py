"""Desktop alerts (no new dependencies — tkinter + winsound are stdlib)."""
import sys


def alert(title: str, message: str) -> None:
    print(f"\n*** ALERT: {title} ***\n{message}\n")
    # Sound
    try:
        import winsound
        winsound.Beep(880, 400)
        winsound.Beep(1175, 400)
    except Exception:
        print("\a")  # terminal bell fallback
    # Popup window
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception as e:
        print(f"[notify] popup skipped: {e}", file=sys.stderr)
