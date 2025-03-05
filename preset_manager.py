import os
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QMessageBox,
                             QListWidget, QFileDialog)

class PresetManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.presets_file = os.path.join(self.plugin_dir, "grd2stream_presets.json")
        self.presets = self.load_presets()

    def load_presets(self):
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading presets: {e}")
                return {}
        return {}

    def save_presets(self):
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving presets: {e}")
            return False

    def save_preset(self, name, preset_data):
        self.presets[name] = preset_data
        return self.save_presets()

    def get_preset(self, name):
        return self.presets.get(name, None)

    def delete_preset(self, name):
        if name in self.presets:
            del self.presets[name]
            return self.save_presets()
        return False

    def get_preset_names(self):
        return list(self.presets.keys())

    def export_preset(self, name, filepath):
        if name in self.presets:
            try:
                with open(filepath, 'w') as f:
                    json.dump({name: self.presets[name]}, f, indent=4)
                return True
            except Exception as e:
                print(f"Error exporting preset: {e}")
        return False

    def import_preset(self, filepath):
        try:
            with open(filepath, 'r') as f:
                imported_presets = json.load(f)
                for name, data in imported_presets.items():
                    self.presets[name] = data
            return self.save_presets()
        except Exception as e:
            print(f"Error importing preset: {e}")
            return False


class PresetDialog(QDialog):
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.setWindowTitle("grd2stream Presets Manager")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        self.preset_list = QListWidget()
        self.update_preset_list()
        layout.addWidget(QLabel("Available Presets:"))
        layout.addWidget(self.preset_list)

        button_layout = QHBoxLayout()

        self.load_button = QPushButton("Load Selected")
        self.load_button.clicked.connect(self.load_preset)
        button_layout.addWidget(self.load_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_preset)
        button_layout.addWidget(self.delete_button)

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_preset)
        button_layout.addWidget(self.export_button)

        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.import_preset)
        button_layout.addWidget(self.import_button)

        layout.addLayout(button_layout)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.close_button)

        self.setLayout(layout)

    def update_preset_list(self):
        self.preset_list.clear()
        self.preset_list.addItems(self.preset_manager.get_preset_names())

    def load_preset(self):
        selected_items = self.preset_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a preset to load.")
            return

        preset_name = selected_items[0].text()
        self.selected_preset = preset_name
        self.accept()

    def delete_preset(self):
        selected_items = self.preset_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a preset to delete.")
            return

        preset_name = selected_items[0].text()
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.preset_manager.delete_preset(preset_name):
                self.update_preset_list()
                QMessageBox.information(self, "Success", f"Preset '{preset_name}' deleted successfully.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to delete preset '{preset_name}'.")

    def export_preset(self):
        selected_items = self.preset_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a preset to export.")
            return

        preset_name = selected_items[0].text()
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Preset",
            os.path.expanduser("~"),
            "JSON Files (*.json)"
        )

        if filepath:
            if not filepath.endswith('.json'):
                filepath += '.json'

            if self.preset_manager.export_preset(preset_name, filepath):
                QMessageBox.information(self, "Success", f"Preset '{preset_name}' exported successfully.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to export preset '{preset_name}'.")

    def import_preset(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Preset",
            os.path.expanduser("~"),
            "JSON Files (*.json)"
        )

        if filepath:
            if self.preset_manager.import_preset(filepath):
                self.update_preset_list()
                QMessageBox.information(self, "Success", "Preset(s) imported successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to import preset(s).")


class SavePresetDialog(QDialog):
    def __init__(self, preset_manager, preset_data, parent=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.preset_data = preset_data
        self.setWindowTitle("Save Preset")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Enter a name for this preset:"))
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Or overwrite existing preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_manager.get_preset_names())
        layout.addWidget(self.preset_combo)

        button_layout = QHBoxLayout()

        self.save_new_button = QPushButton("Save New")
        self.save_new_button.clicked.connect(self.save_new)
        button_layout.addWidget(self.save_new_button)

        self.overwrite_button = QPushButton("Overwrite")
        self.overwrite_button.clicked.connect(self.overwrite)
        button_layout.addWidget(self.overwrite_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_new(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Empty Name", "Please enter a name for the preset.")
            return

        if name in self.preset_manager.get_preset_names():
            reply = QMessageBox.question(
                self,
                "Preset Exists",
                f"Preset '{name}' already exists. Overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        if self.preset_manager.save_preset(name, self.preset_data):
            QMessageBox.information(self, "Success", f"Preset '{name}' saved successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", f"Failed to save preset '{name}'.")

    def overwrite(self):
        if self.preset_combo.count() == 0:
            QMessageBox.warning(self, "No Presets", "There are no existing presets to overwrite.")
            return

        name = self.preset_combo.currentText()
        reply = QMessageBox.question(
            self,
            "Confirm Overwrite",
            f"Are you sure you want to overwrite preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.preset_manager.save_preset(name, self.preset_data):
                QMessageBox.information(self, "Success", f"Preset '{name}' overwritten successfully.")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", f"Failed to overwrite preset '{name}'.")