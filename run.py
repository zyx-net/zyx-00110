import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import DeviceInspectionApp
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceInspectionApp(root)
    root.mainloop()
