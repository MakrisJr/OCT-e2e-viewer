"""
app.py

A small Tkinter desktop app for scrolling through the B-scans of a Heyex
.E2E OCT file, with the current B-scan's position marked on the en-face
fundus image.
"""

import sys
import tkinter as tk
from importlib.resources import files
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .loader import E2EVolume, load_e2e

WHEEL_STEP = 1
PAGE_STEP = 10


class Viewer(tk.Tk):
    def __init__(self, initial_path=None):
        super().__init__()
        self.title("OCT E2E Viewer")
        self.geometry("1100x650")
        self._set_icon()

        self.volume: E2EVolume | None = None
        self.index = 0
        self._updating_controls = False

        self._build_menu()
        self._build_figure()
        self._build_controls()
        self._build_status_bar()
        self._bind_keys()

        if initial_path:
            self.open_path(initial_path)

    def _set_icon(self):
        icon_path = files("oct_e2e_viewer") / "resources" / "icon.png"
        self._icon_image = tk.PhotoImage(file=icon_path)
        self.iconphoto(True, self._icon_image)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open...", command=self._on_open, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def _build_figure(self):
        self.figure = Figure(figsize=(10, 5.5))
        self.ax_fundus = self.figure.add_subplot(1, 2, 1)
        self.ax_bscan = self.figure.add_subplot(1, 2, 2)
        for ax in (self.ax_fundus, self.ax_bscan):
            ax.set_xticks([])
            ax.set_yticks([])

        self.fundus_image = None
        self.bscan_image = None
        self.position_line = None

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _build_controls(self):
        frame = ttk.Frame(self)
        frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

        ttk.Button(frame, text="< Prev", command=lambda: self._step(-1)).pack(side=tk.LEFT)
        ttk.Button(frame, text="Next >", command=lambda: self._step(1)).pack(side=tk.LEFT, padx=(4, 12))

        self.slider = ttk.Scale(frame, from_=0, to=0, orient=tk.HORIZONTAL, command=self._on_slider)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        self.index_var = tk.StringVar(value="0")
        entry = ttk.Entry(frame, textvariable=self.index_var, width=6, justify=tk.RIGHT)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", self._on_entry)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Open a .E2E file to begin (File > Open, or Ctrl+O).")
        ttk.Label(self, textvariable=self.status_var, anchor=tk.W, relief=tk.SUNKEN).pack(
            side=tk.BOTTOM, fill=tk.X
        )

    def _bind_keys(self):
        self.bind("<Control-o>", lambda e: self._on_open())
        self.bind("<Control-q>", lambda e: self.destroy())
        self.bind("<Left>", lambda e: self._step(-1))
        self.bind("<Right>", lambda e: self._step(1))
        self.bind("<Prior>", lambda e: self._step(-PAGE_STEP))  # Page Up
        self.bind("<Next>", lambda e: self._step(PAGE_STEP))  # Page Down
        # Linux mouse wheel events; <MouseWheel> covers Windows/macOS.
        self.canvas.get_tk_widget().bind("<Button-4>", lambda e: self._step(-WHEEL_STEP))
        self.canvas.get_tk_widget().bind("<Button-5>", lambda e: self._step(WHEEL_STEP))
        self.canvas.get_tk_widget().bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self._step(-WHEEL_STEP if event.delta > 0 else WHEEL_STEP)

    # ------------------------------------------------------------------ #
    # File loading
    # ------------------------------------------------------------------ #
    def _on_open(self):
        path = filedialog.askopenfilename(
            title="Open .E2E file",
            filetypes=[("Heyex E2E files", "*.e2e *.E2E"), ("All files", "*.*")],
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        path = Path(path)
        self.status_var.set(f"Loading {path.name}...")
        self.update_idletasks()
        try:
            self.volume = load_e2e(path)
        except Exception as exc:
            messagebox.showerror("Failed to load file", f"Could not load {path.name}:\n\n{exc}")
            self.status_var.set("Open a .E2E file to begin (File > Open, or Ctrl+O).")
            return

        self.title(f"OCT E2E Viewer — {path.name}")
        self.index = self.volume.n_bscans // 2
        self.slider.configure(to=self.volume.n_bscans - 1)

        self._draw_fundus()
        self._redraw()

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def _draw_fundus(self):
        self.ax_fundus.clear()
        self.ax_fundus.set_xticks([])
        self.ax_fundus.set_yticks([])
        fundus = self.volume.fundus
        self.position_line = None
        if fundus is None:
            self.ax_fundus.text(0.5, 0.5, "No fundus image", ha="center", va="center")
        else:
            self.ax_fundus.imshow(fundus, cmap="gray")
            self.ax_fundus.set_title("Fundus")
            (self.position_line,) = self.ax_fundus.plot([], [], color="lime", linewidth=1.5)

    def _redraw(self):
        if self.volume is None:
            return

        bscan = self.volume.bscan(self.index)
        if self.bscan_image is None:
            self.bscan_image = self.ax_bscan.imshow(bscan, cmap="gray")
        else:
            self.bscan_image.set_data(bscan)
            self.bscan_image.set_clim(bscan.min(), bscan.max())
        self.ax_bscan.set_title(f"B-scan {self.index}/{self.volume.n_bscans - 1}")

        if self.position_line is not None:
            line = self.volume.bscan_line(self.index)
            if line is not None:
                (x0, y0), (x1, y1) = line
                self.position_line.set_data([x0, x1], [y0, y1])

        self.canvas.draw_idle()
        self._update_controls()
        self._update_status()

    def _update_controls(self):
        self._updating_controls = True
        self.slider.set(self.index)
        self.index_var.set(str(self.index))
        self._updating_controls = False

    def _update_status(self):
        parts = [self.volume.path.name, f"slice {self.index}/{self.volume.n_bscans - 1}"]
        if self.volume.laterality:
            parts.append(f"laterality: {self.volume.laterality}")
        self.status_var.set("  |  ".join(parts))

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _set_index(self, index):
        if self.volume is None:
            return
        self.index = max(0, min(self.volume.n_bscans - 1, int(index)))
        self._redraw()

    def _step(self, delta):
        if self.volume is None:
            return
        self._set_index(self.index + delta)

    def _on_slider(self, value):
        if self._updating_controls or self.volume is None:
            return
        self._set_index(round(float(value)))

    def _on_entry(self, _event):
        try:
            idx = int(self.index_var.get())
        except ValueError:
            self.index_var.set(str(self.index))
            return
        self._set_index(idx)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--install-desktop-entry":
        from .desktop_integration import install_desktop_entry

        install_desktop_entry()
        return
    initial_path = argv[0] if argv else None
    app = Viewer(initial_path=initial_path)
    app.mainloop()


if __name__ == "__main__":
    main()
