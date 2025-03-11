import os
import json
import datetime
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLineEdit, QLabel, QFormLayout,
                             QMessageBox, QCheckBox, QDialogButtonBox, QGroupBox, QComboBox, QWidget, QListWidgetItem)


class PresetManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.presets_file = os.path.join(plugin_dir, "presets.json")
        self.presets = self.load_presets()

    def load_presets(self):
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_presets(self):
        with open(self.presets_file, 'w') as f:
            json.dump(self.presets, f, indent=4)

    def add_preset(self, name, data):
        self.presets[name] = data
        self.save_presets()

    def update_preset(self, name, data):
        if name in self.presets:
            self.presets[name] = data
            self.save_presets()
            return True
        return False

    def delete_preset(self, name):
        if name in self.presets:
            del self.presets[name]
            self.save_presets()
            return True
        return False

    def get_preset(self, name):
        return self.presets.get(name)

    def get_preset_names(self):
        return list(self.presets.keys())


class PresetItemWidget(QWidget):
    def __init__(self, preset_name, preset_data, parent=None):
        super(PresetItemWidget, self).__init__(parent)
        self.preset_name = preset_name
        self.preset_data = preset_data

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        name_label = QLabel(preset_name)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)

        last_edited = preset_data.get('last_edited', 'Never')
        edit_info = f"last edited: {last_edited}"

        details_label = QLabel(edit_info)
        details_label.setStyleSheet("font-size: 8pt; color: gray;")
        layout.addWidget(details_label)

        self.setToolTip(self._build_tooltip())

    def _build_tooltip(self):
        tooltip = f"<b>Raster 1:</b> {self.preset_data.get('raster_1_name', 'Unknown')} (Band {self.preset_data.get('band_1', 1)})<br>"
        tooltip += f"<b>Raster 2:</b> {self.preset_data.get('raster_2_name', 'Unknown')} (Band {self.preset_data.get('band_2', 1)})<br>"
        tooltip += f"<b>Backward Steps:</b> {'Yes' if self.preset_data.get('backward_steps', False) else 'No'}<br>"
        if self.preset_data.get('step_size') is not None:
            tooltip += f"<b>Step Size:</b> {self.preset_data.get('step_size')}<br>"
        else:
            tooltip += "<b>Step Size:</b> Δ = min(x_inc, y_inc) / 5 [default]<br>"
        if self.preset_data.get('max_integration_time') is not None:
            tooltip += f"<b>Max Integration Time:</b> {self.preset_data.get('max_integration_time')}<br>"
        else:
            tooltip += "<b>Max Integration Time:</b> / [default]<br>"
        if self.preset_data.get('max_steps') is not None:
            tooltip += f"<b>Max Steps:</b> {self.preset_data.get('max_steps')}<br>"
        else:
            tooltip += "<b>Max Steps:</b> 10,000 [default]<br>"
        output_format = self.preset_data.get('output_format')
        if output_format == "-l":
            format_str = "x y dist v_x v_y"
        elif output_format == "-t":
            format_str = "x y dist v_x v_y time"
        else:
            format_str = "x y dist [default]"
        tooltip += f"<b>Output Format:</b> {format_str}"
        return tooltip


class PresetDialog(QDialog):
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.selected_preset = None
        self.setWindowTitle("Preset Manager")
        self.resize(400, 300)
        layout = QVBoxLayout(self)
        self.preset_list = QListWidget()
        self.preset_list.setMouseTracking(True)
        self.populate_preset_list()
        layout.addWidget(QLabel("Select a preset:"))
        layout.addWidget(self.preset_list)

        button_layout = QHBoxLayout()
        self.select_button = QPushButton("Select")
        self.select_button.clicked.connect(self.select_preset)
        self.view_edit_button = QPushButton("View/Edit")
        self.view_edit_button.clicked.connect(self.view_edit_preset)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_preset)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.view_edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def populate_preset_list(self):
        self.preset_list.clear()
        for preset_name in self.preset_manager.get_preset_names():
            preset_data = self.preset_manager.get_preset(preset_name)
            list_item = QListWidgetItem(self.preset_list)
            item_widget = PresetItemWidget(preset_name, preset_data)
            list_item.setSizeHint(item_widget.sizeHint())
            self.preset_list.addItem(list_item)
            self.preset_list.setItemWidget(list_item, item_widget)

    def select_preset(self):
        current_item = self.preset_list.currentItem()
        if current_item:
            item_widget = self.preset_list.itemWidget(current_item)
            self.selected_preset = item_widget.preset_name
            self.accept()
        else:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset first.")

    def view_edit_preset(self):
        current_item = self.preset_list.currentItem()
        if current_item:
            item_widget = self.preset_list.itemWidget(current_item)
            preset_name = item_widget.preset_name
            preset_data = self.preset_manager.get_preset(preset_name)
            dialog = EditPresetDialog(preset_name, preset_data, self.preset_manager, self)
            if dialog.exec_() == QDialog.Accepted:
                self.populate_preset_list()
        else:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset first.")

    def delete_preset(self):
        current_item = self.preset_list.currentItem()
        if current_item:
            item_widget = self.preset_list.itemWidget(current_item)
            preset_name = item_widget.preset_name
            reply = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete the preset '{preset_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.preset_manager.delete_preset(preset_name)
                self.populate_preset_list()
        else:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset first.")


class EditPresetDialog(QDialog):
    def __init__(self, preset_name, preset_data, preset_manager, parent=None):
        super().__init__(parent)
        self.preset_name = preset_name
        self.preset_data = preset_data
        self.preset_manager = preset_manager
        self.setWindowTitle(f"Edit Preset")
        self.resize(500, 400)
        layout = QVBoxLayout(self)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(preset_name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        param_group = QGroupBox("Parameters")
        param_layout = QFormLayout(param_group)

        raster1_label = QLabel(f"{preset_data.get('raster_1_name', 'Unknown')} (Band {preset_data.get('band_1', 1)})")
        raster2_label = QLabel(f"{preset_data.get('raster_2_name', 'Unknown')} (Band {preset_data.get('band_2', 1)})")
        param_layout.addRow("Raster 1:", raster1_label)
        param_layout.addRow("Raster 2:", raster2_label)

        self.backward_checkbox = QCheckBox()
        self.backward_checkbox.setChecked(preset_data.get('backward_steps', False))
        param_layout.addRow("Backward Steps:", self.backward_checkbox)
        self.step_size_edit = QLineEdit()
        if preset_data.get('step_size') is not None:
            self.step_size_edit.setText(str(preset_data.get('step_size')))
        param_layout.addRow("Step Size:", self.step_size_edit)
        self.max_time_edit = QLineEdit()
        if preset_data.get('max_integration_time') is not None:
            self.max_time_edit.setText(str(preset_data.get('max_integration_time')))
        param_layout.addRow("Max Integration Time:", self.max_time_edit)
        self.max_steps_edit = QLineEdit()
        if preset_data.get('max_steps') is not None:
            self.max_steps_edit.setText(str(preset_data.get('max_steps')))
        param_layout.addRow("Max Steps:", self.max_steps_edit)
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItem("x y dist (default)", None)
        self.output_format_combo.addItem("x y dist v_x v_y", "-l")
        self.output_format_combo.addItem("x y dist v_x v_y time", "-t")
        output_format = preset_data.get('output_format')
        for i in range(self.output_format_combo.count()):
            if self.output_format_combo.itemData(i) == output_format:
                self.output_format_combo.setCurrentIndex(i)
                break
        param_layout.addRow("Output Format:", self.output_format_combo)
        layout.addWidget(param_group)
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_changes)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def save_changes(self):
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Invalid Name", "Preset name cannot be empty.")
            return
        if new_name != self.preset_name and new_name in self.preset_manager.get_preset_names():
            reply = QMessageBox.question(
                self,
                "Preset Name Exists",
                f"A preset with the name '{new_name}' already exists. Do you want to overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        updated_data = self.preset_data.copy()
        updated_data['backward_steps'] = self.backward_checkbox.isChecked()

        error_message = None

        if self.step_size_edit.text():
            if ',' in self.step_size_edit.text():
                error_message = "Please use a period (.) instead of a comma (,) as decimal separator in 'Step Size'."
            else:
                try:
                    updated_data['step_size'] = float(self.step_size_edit.text())
                except ValueError:
                    error_message = "Invalid 'Step Size'. Please enter a valid number."
        else:
            updated_data['step_size'] = None
        if self.max_time_edit.text():
            if ',' in self.max_time_edit.text():
                error_message = "Please use a period (.) instead of a comma (,) as decimal separator in 'Max Integration Time'."
            else:
                try:
                    updated_data['max_integration_time'] = float(self.max_time_edit.text())
                except ValueError:
                    error_message = "Invalid 'Maximum Integration Time'. Please enter a valid number."
        else:
            updated_data['max_integration_time'] = None
        if self.max_steps_edit.text():
            try:
                updated_data['max_steps'] = int(self.max_steps_edit.text())
            except ValueError:
                error_message = "Invalid 'Maximum Number of Steps'. Please enter a valid integer."
        else:
            updated_data['max_steps'] = None

        if error_message:
            QMessageBox.warning(self,"Invalid Input", error_message)
            return False

        updated_data['output_format'] = self.output_format_combo.currentData()
        updated_data['last_edited'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if new_name != self.preset_name:
            self.preset_manager.delete_preset(self.preset_name)
            self.preset_manager.add_preset(new_name, updated_data)
        else:
            self.preset_manager.update_preset(self.preset_name, updated_data)
        QMessageBox.information(self, "Success", "Preset updated successfully.")
        self.accept()


class SavePresetDialog(QDialog):
    def __init__(self, preset_manager, preset_data, parent=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.preset_data = preset_data
        self.setWindowTitle("Save Preset")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter a name for this preset:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        summary_group = QGroupBox("Settings to Save")
        summary_layout = QVBoxLayout(summary_group)

        raster1_name = preset_data.get('raster_1_name', 'Unknown')
        raster2_name = preset_data.get('raster_2_name', 'Unknown')
        summary_text = f"Raster 1: {raster1_name} (Band {preset_data.get('band_1', 1)})\n"
        summary_text += f"Raster 2: {raster2_name} (Band {preset_data.get('band_2', 1)})\n"
        summary_text += f"Backward Steps: {'Yes' if preset_data.get('backward_steps', False) else 'No'}\n"

        if preset_data.get('step_size') is not None:
            summary_text += f"Step Size: {preset_data.get('step_size')}\n"
        else:
            summary_text += "Step Size: Δ = min(x_inc, y_inc) / 5 [default]\n"
        if preset_data.get('max_integration_time') is not None:
            summary_text += f"Max Integration Time: {preset_data.get('max_integration_time')}\n"
        else:
            summary_text += "Max Integration Time: / [default]\n"
        if preset_data.get('max_steps') is not None:
            summary_text += f"Max Steps: {preset_data.get('max_steps')}\n"
        else:
            summary_text += "Max Steps: 10,000 [default]\n"
        output_format = preset_data.get('output_format')
        if output_format == "-l":
            format_str = "x y dist v_x v_y"
        elif output_format == "-t":
            format_str = "x y dist v_x v_y time"
        else:
            format_str = "x y dist [default]"

        summary_text += f"Output Format: {format_str}"
        summary_label = QLabel(summary_text)
        summary_layout.addWidget(summary_label)
        layout.addWidget(summary_group)
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_preset)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def save_preset(self):
        preset_name = self.name_edit.text().strip()
        if not preset_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid preset name.")
            return
        if preset_name in self.preset_manager.get_preset_names():
            reply = QMessageBox.question(
                self,
                "Preset Already Exists",
                f"A preset with the name '{preset_name}' already exists. Do you want to edit it instead?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                edit_dialog = EditPresetDialog(preset_name, self.preset_manager.get_preset(preset_name),
                                               self.preset_manager, self)
                self.reject()
                edit_dialog.exec_()
                return
            else:
                return

        preset_data_with_timestamp = self.preset_data.copy()
        preset_data_with_timestamp['last_edited'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.preset_manager.add_preset(preset_name, preset_data_with_timestamp)
        QMessageBox.information(self, "Success", f"Preset '{preset_name}' saved successfully.")
        self.accept()
