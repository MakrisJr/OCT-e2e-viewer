"""
app.py

A small Qt desktop app for scrolling through the B-scans of a Heyex
.E2E OCT file, with the current B-scan's position marked on the en-face
fundus image.
"""

import sys
from importlib.resources import files
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qt_material import apply_stylesheet

from .loader import E2EVolume, load_e2e
from .recent_files import add_recent_file, clear_recent_files, load_recent_files

WHEEL_STEP = 1
PAGE_STEP = 10


def _recent_label(path):
    path = Path(path)
    try:
        return str(Path("~") / path.relative_to(Path.home()))
    except ValueError:
        return str(path)


class Viewer(QMainWindow):
    def __init__(self, initial_path=None):
        super().__init__()
        self.setWindowTitle("OCT E2E Viewer")
        self.resize(1100, 650)
        self._set_icon()

        self.volume: E2EVolume | None = None
        self.index = 0
        self._updating_controls = False

        self.fundus_image = None
        self.bscan_image = None
        self.position_line = None
        self.layer_lines = []

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

        self._build_view_stack(layout)
        self._build_controls(layout)
        self._build_menu()
        self._bind_shortcuts()
        self.statusBar().showMessage("Open a .E2E file to begin (File > Open, or Ctrl+O).")

        if initial_path:
            self.open_path(initial_path)

    def _set_icon(self):
        icon_path = files("oct_e2e_viewer") / "resources" / "icon.png"
        self.setWindowIcon(QIcon(str(icon_path)))

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        self.recent_menu = file_menu.addMenu("Open Recent")
        self._refresh_recent_menu()

        export_action = QAction("&Export as PNG...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        self._populate_recent_menu(self.recent_menu)

    def _populate_recent_menu(self, menu):
        recent = load_recent_files()
        if not recent:
            action = menu.addAction("(No recent files)")
            action.setEnabled(False)
            return
        for path in recent:
            action = menu.addAction(_recent_label(path))
            action.triggered.connect(lambda checked=False, p=path: self.open_path(p))
        menu.addSeparator()
        menu.addAction("Clear Recent Files", self._on_clear_recent)

    def _on_clear_recent(self):
        clear_recent_files()
        self._refresh_recent_menu()

    def _build_view_stack(self, layout):
        self.view_stack = QStackedWidget()
        self._build_empty_state()
        self._build_figure()
        self.view_stack.addWidget(self.empty_state)
        self.view_stack.addWidget(self.chart_widget)
        layout.addWidget(self.view_stack, stretch=1)

    def _build_empty_state(self):
        self.empty_state = QWidget()
        outer = QVBoxLayout(self.empty_state)
        outer.addStretch(1)

        label = QLabel("No file open")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16pt;")
        outer.addWidget(label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        open_btn = QPushButton("Open File...")
        open_btn.clicked.connect(self._on_open)
        button_row.addWidget(open_btn)

        recent_btn = QPushButton("Open Recent...")
        recent_btn.clicked.connect(lambda: self._show_recent_menu(recent_btn))
        button_row.addWidget(recent_btn)

        button_row.addStretch(1)
        outer.addLayout(button_row)
        outer.addStretch(1)

    def _show_recent_menu(self, anchor_widget):
        menu = QMenu(self)
        self._populate_recent_menu(menu)
        menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))

    def _build_figure(self):
        self.chart_widget = QWidget()
        chart_layout = QVBoxLayout(self.chart_widget)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(10, 5.5))
        self.ax_fundus = self.figure.add_subplot(1, 2, 1)
        self.ax_bscan = self.figure.add_subplot(1, 2, 2)
        for ax in (self.ax_fundus, self.ax_bscan):
            ax.set_xticks([])
            ax.set_yticks([])

        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.wheelEvent = self._on_canvas_wheel
        self.toolbar = NavigationToolbar2QT(self.canvas, self.chart_widget)

        chart_layout.addWidget(self.toolbar)
        chart_layout.addWidget(self.canvas, stretch=1)

    def _build_controls(self, layout):
        frame = QWidget()
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 4, 8, 4)

        prev_btn = QPushButton("< Prev")
        prev_btn.clicked.connect(lambda: self._step(-1))
        row.addWidget(prev_btn)

        next_btn = QPushButton("Next >")
        next_btn.clicked.connect(lambda: self._step(1))
        row.addWidget(next_btn)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self._on_slider)
        row.addWidget(self.slider, stretch=1)

        self.index_edit = QLineEdit("0")
        self.index_edit.setFixedWidth(50)
        self.index_edit.setAlignment(Qt.AlignRight)
        self.index_edit.returnPressed.connect(self._on_entry)
        row.addWidget(self.index_edit)

        self.layers_checkbox = QCheckBox("Layer annotations")
        self.layers_checkbox.setChecked(True)
        self.layers_checkbox.stateChanged.connect(lambda _state: self._redraw())
        row.addWidget(self.layers_checkbox)

        layout.addWidget(frame)

    def _bind_shortcuts(self):
        # Left/Right/PageUp/PageDown/Home/End navigate B-scans from anywhere
        # in the window; Qt automatically defers to a focused text field
        # (e.g. the index entry) for its own cursor movement instead of
        # firing these, via its shortcut-override handling.
        self._shortcuts = [
            QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self._step(-WHEEL_STEP)),
            QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self._step(WHEEL_STEP)),
            QShortcut(QKeySequence(Qt.Key_PageUp), self, activated=lambda: self._step(-PAGE_STEP)),
            QShortcut(QKeySequence(Qt.Key_PageDown), self, activated=lambda: self._step(PAGE_STEP)),
            QShortcut(QKeySequence(Qt.Key_Home), self, activated=lambda: self._set_index(0)),
            QShortcut(QKeySequence(Qt.Key_End), self, activated=lambda: self._set_index(self.volume.n_bscans - 1 if self.volume else 0)),
        ]

    def _on_canvas_wheel(self, event):
        delta = event.angleDelta().y()
        self._step(-WHEEL_STEP if delta > 0 else WHEEL_STEP)
        event.accept()

    # ------------------------------------------------------------------ #
    # File loading
    # ------------------------------------------------------------------ #
    def _on_open(self):
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open .E2E file",
            str(Path.home()),
            "Heyex E2E files (*.e2e *.E2E);;All files (*)",
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        path = Path(path)
        self.statusBar().showMessage(f"Loading {path.name}...")
        QApplication.processEvents()
        try:
            self.volume = load_e2e(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to load file", f"Could not load {path.name}:\n\n{exc}")
            self.statusBar().showMessage("Open a .E2E file to begin (File > Open, or Ctrl+O).")
            return

        add_recent_file(path)
        self._refresh_recent_menu()
        self.view_stack.setCurrentWidget(self.chart_widget)

        self.setWindowTitle(f"OCT E2E Viewer — {path.name}")
        self.index = self.volume.n_bscans // 2
        self.slider.setMaximum(self.volume.n_bscans - 1)

        self._draw_fundus()
        self._redraw()
        # Reset the toolbar's zoom/pan history so "Home" returns to the
        # newly loaded image instead of the empty axes from app startup.
        self.toolbar.update()

    def _on_export(self):
        if self.volume is None:
            QMessageBox.information(self, "Export as PNG", "Open a .E2E file first.")
            return

        default_name = f"{self.volume.path.stem}_bscan{self.index}.png"
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export as PNG",
            str(Path.home() / default_name),
            "PNG image (*.png);;All files (*)",
        )
        if not path:
            return
        if not Path(path).suffix:
            path += ".png"

        try:
            self.figure.savefig(path, dpi=150)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to export", f"Could not save {path}:\n\n{exc}")
            return

        self.statusBar().showMessage(f"Exported to {path}")

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
        same_shape = self.bscan_image is not None and self.bscan_image.get_array().shape == bscan.shape
        if same_shape:
            # Preserve whatever zoom/pan the user set via the toolbar instead
            # of snapping back out on every navigation step.
            prev_xlim = self.ax_bscan.get_xlim()
            prev_ylim = self.ax_bscan.get_ylim()

        if self.bscan_image is None:
            self.bscan_image = self.ax_bscan.imshow(bscan, cmap="gray")
        else:
            self.bscan_image.set_data(bscan)
            self.bscan_image.set_clim(bscan.min(), bscan.max())
        self.ax_bscan.set_title(f"B-scan {self.index}/{self.volume.n_bscans - 1}")

        for line in self.layer_lines:
            line.remove()
        self.layer_lines = []
        if self.layers_checkbox.isChecked():
            for name, heights in self.volume.bscan_layers(self.index).items():
                (line,) = self.ax_bscan.plot(heights, linewidth=1, label=name)
                self.layer_lines.append(line)
        # Layer lines have no sticky edges, so they can nudge autoscale into
        # zooming out slightly; pin the view back to the image extent (or the
        # user's current zoom, if the B-scan dimensions haven't changed).
        if same_shape:
            self.ax_bscan.set_xlim(prev_xlim)
            self.ax_bscan.set_ylim(prev_ylim)
        else:
            self.ax_bscan.set_xlim(-0.5, bscan.shape[1] - 0.5)
            self.ax_bscan.set_ylim(bscan.shape[0] - 0.5, -0.5)

        if self.position_line is not None:
            line = self.volume.bscan_line(self.index)
            if line is not None:
                (x0, y0), (x1, y1) = line
                self.position_line.set_data([x0, x1], [y0, y1])

        self.canvas.draw_idle()
        self._update_controls()
        self._update_status(bscan.shape)

    def _update_controls(self):
        self._updating_controls = True
        self.slider.setValue(self.index)
        self.index_edit.setText(str(self.index))
        self._updating_controls = False

    def _update_status(self, bscan_shape):
        parts = [self.volume.path.name, f"slice {self.index}/{self.volume.n_bscans - 1}"]
        if self.volume.laterality:
            parts.append(f"eye: {self.volume.laterality}")
        if self.volume.scan_date:
            parts.append(f"scanned: {self.volume.scan_date:%Y-%m-%d %H:%M}")
        quality = self.volume.bscan_quality(self.index)
        if quality is not None:
            parts.append(f"quality: {quality:.2f}")
        num_averages = self.volume.bscan_num_averages(self.index)
        if num_averages is not None:
            parts.append(f"averaging: {num_averages}")
        axial_scale = self.volume.axial_scale_um
        if axial_scale is not None:
            parts.append(f"axial: {axial_scale:.2f} µm/px")
        parts.append(f"{bscan_shape[1]}x{bscan_shape[0]} px")
        self.statusBar().showMessage("  |  ".join(parts))

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
        self._set_index(value)

    def _on_entry(self):
        try:
            idx = int(self.index_edit.text())
        except ValueError:
            self.index_edit.setText(str(self.index))
            return
        self._set_index(idx)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--install-desktop-entry":
        from .desktop_integration import install_desktop_entry

        install_desktop_entry()
        return

    initial_path = argv[0] if argv else None
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="light_blue.xml")
    window = Viewer(initial_path=initial_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
