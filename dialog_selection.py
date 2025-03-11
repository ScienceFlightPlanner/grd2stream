from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QHBoxLayout,
                             QMessageBox)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, Qgis, QgsRasterLayer

from .dialog_preset import PresetDialog
from .help_widget import show_help


class SelectionDialog(QDialog):
    def __init__(self, iface, flowline_module_instance=None):
        super().__init__(parent=None)
        self.iface = iface
        self.flowline_module = flowline_module_instance
        self.help_widget = None
        self.setWindowTitle("Select your GDAL grids (e.g., NetCDF, GTiFF, etc.)")
        self.setMinimumWidth(400)

        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.backward_steps = False
        self.step_size = None
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        if self.flowline_module:
            preset_layout = QHBoxLayout()

            self.use_last_button = QPushButton("Use Last Settings")
            self.use_last_button.clicked.connect(self.use_last_settings)
            preset_layout.addWidget(self.use_last_button)

            self.load_preset_button = QPushButton("Load Preset")
            self.load_preset_button.clicked.connect(self.manage_presets)
            preset_layout.addWidget(self.load_preset_button)

            preset_layout.addStretch()

            self.help_button = QPushButton()
            self.help_button.setIcon(QIcon(":/plugins/grd_2_stream/resources/icons/help.svg"))
            self.help_button.setToolTip("Help")
            self.help_button.setFixedSize(28, 28)
            self.help_button.clicked.connect(lambda: show_help(self.iface))
            preset_layout.addWidget(self.help_button)

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

    def show_help(self):
        self.help_widget = show_help(self.iface, self.help_widget)

    def closeEvent(self, event):
        if self.help_widget is not None and self.help_widget.isVisible():
            self.help_widget.close()
        super().closeEvent(event)

    def save_preset(self):
        if self.update_from_dialog():
            self.flowline_module.save_current_settings()

    def manage_presets(self):
        """Open the preset management dialog and apply selected preset to form elements"""
        if self.flowline_module:
            original_preset = getattr(self.flowline_module, 'last_used_preset', None) # TODO

            dialog = PresetDialog(self.flowline_module.preset_manager)

            if dialog.exec_() == QDialog.Accepted:
                preset_name = getattr(dialog, 'selected_preset', None)
                if preset_name:
                    preset_data = self.flowline_module.preset_manager.get_preset(preset_name)
                    if preset_data:
                        self.apply_preset_to_ui(preset_data)

                        self.flowline_module.last_used_preset = preset_name

                        self.iface.messageBar().pushMessage(
                            "Success",
                            f"Preset '{preset_name}' loaded into form.",
                            level=Qgis.Info,
                            duration=5
                        )
                    else:
                        QMessageBox.warning(
                            None,
                            "Error",
                            f"Could not load preset '{preset_name}'."
                        )

    def apply_preset_to_ui(self, preset_data):
        """Apply preset data to the UI elements"""
        self.select_raster_in_combobox(
            self.layer_box_1,
            preset_data.get('raster_1_name'),
            preset_data.get('band_1', 1)
        )
        self.select_raster_in_combobox(
            self.layer_box_2,
            preset_data.get('raster_2_name'),
            preset_data.get('band_2', 1)
        )

        self.backward_checkbox.setChecked(preset_data.get('backward_steps', False))

        output_format = preset_data.get('output_format')
        for i in range(self.output_format_box.count()):
            if self.output_format_box.itemData(i) == output_format:
                self.output_format_box.setCurrentIndex(i)
                break

        step_size = preset_data.get('step_size')
        if step_size is not None:
            self.manual_step_checkbox.setChecked(True)
            self.step_size_input.setText(str(step_size))
        else:
            self.manual_step_checkbox.setChecked(False)
            self.step_size_input.clear()

        if preset_data.get('max_steps') is not None:
            self.max_steps_input.setText(str(preset_data.get('max_steps')))
        else:
            self.max_steps_input.clear()

        if preset_data.get('max_integration_time') is not None:
            self.max_time_input.setText(str(preset_data.get('max_integration_time')))
        else:
            self.max_time_input.clear()

    def select_raster_in_combobox(self, combobox, layer_name, band=1):
        """Find and select the specified raster and band in a combobox"""
        for i in range(combobox.count()):
            item_text = combobox.itemText(i)
            if item_text.startswith(f"{layer_name} - Band {band}"):
                combobox.setCurrentIndex(i)
                return True
        return False

    def use_last_settings(self):
        if self.flowline_module:
            preset_data = self.flowline_module.use_last_settings()
            if preset_data:
                self.apply_preset_to_ui(preset_data)
                self.iface.messageBar().pushMessage(
                    "Success",
                    "Last used settings loaded into form.",
                    level=Qgis.Info,
                    duration=5
                )
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

        self.step_size = None
        self.max_steps = None
        self.max_integration_time = None

        error_message = None
        if self.manual_step_checkbox.isChecked() and self.step_size_input.text():
            if ',' in self.step_size_input.text():
                error_message = "Please use a period (.) instead of a comma (,) as decimal separator in 'Step Size'."
            else:
                try:
                    self.step_size = float(self.step_size_input.text())
                except ValueError:
                    error_message = "Invalid 'Step Size'. Please enter a valid number."

        if self.max_steps_input.text():
            try:
                self.max_steps = int(self.max_steps_input.text())
            except ValueError:
                error_message = "Invalid 'Maximum Number of Steps'. Please enter a valid integer."

        if self.max_time_input.text():
            if ',' in self.max_time_input.text():
                error_message = "Please use a period (.) instead of a comma (,) as decimal separator in 'Max Integration Time'."
            else:
                try:
                    self.max_integration_time = float(self.max_time_input.text())
                except ValueError:
                    error_message = "Invalid 'Maximum Integration Time'. Please enter a valid number."

        if error_message:
            QMessageBox.warning(
                self,
                "Invalid Input",
                error_message
            )
            return False

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

        return True

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

        validation_failed = False

        if self.manual_step_checkbox.isChecked() and self.step_size_input.text():
            if ',' in self.step_size_input.text():
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please use a period (.) instead of a comma (,) as decimal separator in 'Step Size'."
                )
                validation_failed = True
            else:
                try:
                    self.step_size = float(self.step_size_input.text()) if self.manual_step_checkbox.isChecked() and self.step_size_input.text() else None
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        "Invalid 'Step Size'. Please enter a valid number."
                    )
                    validation_failed = True

        if self.max_steps_input.text():
            try:
                self.max_steps = int(self.max_steps_input.text()) if self.max_steps_input.text() else None
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Invalid 'Maximum Number of Steps'. Please enter a valid integer."
                )
                validation_failed = True

        if self.max_time_input.text():
            if ',' in self.max_time_input.text():
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please use a period (.) instead of a comma (,) as decimal separator in 'Max Integration Time'."
                )
                validation_failed = True
            else:
                try:
                    self.max_integration_time = float(self.max_time_input.text()) if self.max_time_input.text() else None
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        "Invalid 'Maximum Integration Time'. Please enter a valid number."
                    )
                    validation_failed = True

        if validation_failed:
            return

        self.output_format = self.output_format_box.currentData()

        super().accept()
