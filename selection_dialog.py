from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QHBoxLayout,
                             QMessageBox)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, Qgis, QgsRasterLayer

class SelectionDialog(QDialog):
    def __init__(self, iface, flowline_module_instance=None):
        super().__init__(parent=None)
        self.iface = iface
        self.flowline_module = flowline_module_instance
        self.setWindowTitle("Select your GDAL grids (e.g., GMT, NetCDF, GTiFF, etc.)")
        self.setMinimumWidth(400)

        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.backward_steps = False
        self.step_size = None
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None

        layout = QVBoxLayout()

        if self.flowline_module:
            preset_layout = QHBoxLayout()
            self.load_preset_button = QPushButton("Load Preset")
            self.load_preset_button.clicked.connect(self.manage_presets)
            preset_layout.addWidget(self.load_preset_button)
            self.use_last_button = QPushButton("Use Last Settings")
            self.use_last_button.clicked.connect(self.use_last_settings)
            preset_layout.addWidget(self.use_last_button)
            layout.addLayout(preset_layout)
            layout.addSpacing(10)

        layout.addWidget(QLabel("Select the 1st grid layer:"))
        self.layer_box_1 = QComboBox()
        layout.addWidget(self.layer_box_1)
        layout.addWidget(QLabel("Select the 2nd grid layer:"))
        self.layer_box_2 = QComboBox()
        layout.addWidget(self.layer_box_2)

        self.populate_layers()

        self.backward_checkbox = QCheckBox("Backward Steps?")
        layout.addWidget(self.backward_checkbox)

        layout.addWidget(QLabel("Output Format:"))
        self.output_format_box = QComboBox()
        self.output_format_box.addItem("x  y  dist  (default)", None)
        self.output_format_box.addItem("x  y  dist  v_x  v_y", "-l")
        self.output_format_box.addItem("x  y  dist  v_x  v_y  time", "-t")
        layout.addWidget(self.output_format_box)

        layout.addWidget(QLabel("<b>Parameters:</b>"))

        self.manual_step_checkbox = QCheckBox("Manually set Step Size (in m)")
        layout.addWidget(self.manual_step_checkbox)
        self.manual_step_checkbox.stateChanged.connect(self.toggle_step_size_input)
        self.step_size_input = QLineEdit()
        self.step_size_input.setPlaceholderText("default: Δ = min(x_inc, y_inc) / 5")
        self.step_size_input.setEnabled(False)
        layout.addWidget(self.step_size_input)

        self.max_steps_input = QLineEdit()
        self.max_steps_input.setPlaceholderText("default: 10,000")
        layout.addWidget(QLabel("Maximum Number of Steps:"))
        layout.addWidget(self.max_steps_input)

        self.max_time_input = QLineEdit()
        self.max_time_input.setPlaceholderText("default: /")
        layout.addWidget(QLabel("Maximum Integration Time (in s):"))
        layout.addWidget(self.max_time_input)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.save_preset_button = QPushButton("Save as Preset")
        self.save_preset_button.clicked.connect(self.save_preset)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.save_preset_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_preset(self):
        self.update_from_dialog()
        self.flowline_module.save_current_settings()

    def manage_presets(self):
        if self.flowline_module:
            original_preset = getattr(self.flowline_module, 'last_used_preset', None)
            self.flowline_module.manage_presets()
            new_preset = getattr(self.flowline_module, 'last_used_preset', None)
            if new_preset and new_preset != original_preset:
                self.close()

    def use_last_settings(self):
        if self.flowline_module:
            if self.flowline_module.selected_raster_1 and self.flowline_module.selected_raster_2:
                if self.flowline_module.use_last_settings():
                    self.close()
            else:
                QMessageBox.information(None, "No Previous Settings", "Please select input parameters.")

    def update_from_dialog(self):
        index_1 = self.layer_box_1.currentIndex()
        index_2 = self.layer_box_2.currentIndex()

        selected_1 = self.layer_box_1.itemData(index_1)
        selected_2 = self.layer_box_2.itemData(index_2)

        if isinstance(selected_1, tuple):
            self.selected_raster_1, self.selected_band_1 = selected_1
        else:
            self.selected_raster_1 = selected_1
            self.selected_band_1 = 1

        if isinstance(selected_2, tuple):
            self.selected_raster_2, self.selected_band_2 = selected_2
        else:
            self.selected_raster_2 = selected_2
            self.selected_band_2 = 1

        self.backward_steps = self.backward_checkbox.isChecked()
        self.step_size = float(self.step_size_input.text()) if self.manual_step_checkbox.isChecked() and self.step_size_input.text() else None
        self.max_steps = int(self.max_steps_input.text()) if self.max_steps_input.text() else None
        self.max_integration_time = float(self.max_time_input.text()) if self.max_time_input.text() else None
        self.output_format = self.output_format_box.currentData()

        if self.flowline_module:
            self.flowline_module.selected_raster_1 = self.selected_raster_1
            self.flowline_module.selected_raster_2 = self.selected_raster_2
            self.flowline_module.selected_band_1 = self.selected_band_1
            self.flowline_module.selected_band_2 = self.selected_band_2
            self.flowline_module.backward_steps = self.backward_steps
            self.flowline_module.step_size = self.step_size
            self.flowline_module.max_integration_time = self.max_integration_time
            self.flowline_module.max_steps = self.max_steps
            self.flowline_module.output_format = self.output_format

    def toggle_step_size_input(self, state):
        if state == Qt.Checked:
            self.step_size_input.setEnabled(True)
            self.step_size_input.setStyleSheet("color: black;")
        else:
            self.step_size_input.setEnabled(False)
            self.step_size_input.clear()
            self.step_size_input.setStyleSheet("color: gray;")

    def populate_layers(self):
        layers = QgsProject.instance().mapLayers().values()
        raster_layers = [layer for layer in layers if isinstance(layer, QgsRasterLayer)]
        for layer in raster_layers:
            band_count = layer.bandCount()
            if band_count > 1:
                for band in range(1, band_count + 1):
                    self.layer_box_1.addItem(f"{layer.name()} - Band {band}", (layer, band))
                    self.layer_box_2.addItem(f"{layer.name()} - Band {band}", (layer, band))
            else:
                self.layer_box_1.addItem(f"{layer.name()} - Band 1", (layer, 1))
                self.layer_box_2.addItem(f"{layer.name()} - Band 1", (layer, 1))

    def accept(self):
        index_1 = self.layer_box_1.currentIndex()
        index_2 = self.layer_box_2.currentIndex()

        selected_1 = self.layer_box_1.itemData(index_1)
        selected_2 = self.layer_box_2.itemData(index_2)

        if isinstance(selected_1, tuple):
            self.selected_raster_1, self.selected_band_1 = selected_1
        else:
            self.selected_raster_1 = selected_1
            self.selected_band_1 = 1

        if isinstance(selected_2, tuple):
            self.selected_raster_2, self.selected_band_2 = selected_2
        else:
            self.selected_raster_2 = selected_2
            self.selected_band_2 = 1

        if self.selected_raster_1 == self.selected_raster_2 and self.selected_band_1 == self.selected_band_2:
            self.iface.messageBar().pushMessage(
                "Error",
                "Please select two different raster layers/bands.",
                level=Qgis.Critical,
                duration=5
            )
            return

        self.backward_steps = self.backward_checkbox.isChecked()
        self.step_size = float(self.step_size_input.text()) if self.manual_step_checkbox.isChecked() and self.step_size_input.text() else None
        self.max_steps = int(self.max_steps_input.text()) if self.max_steps_input.text() else None
        self.max_integration_time = float(self.max_time_input.text()) if self.max_time_input.text() else None
        self.output_format = self.output_format_box.currentData()

        super().accept()
