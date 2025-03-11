import os
import platform
import subprocess
import tempfile

from qgis.PyQt.QtGui import QIcon
from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtWidgets import (QApplication, QCheckBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QMessageBox, QProgressDialog, QPushButton, QRadioButton, QVBoxLayout)
from qgis.PyQt.QtCore import Qt

from .dialog_preset import PresetManager, SavePresetDialog


class CoordinateInputDialog(QDialog):
    def __init__(self, parent=None, crs=None):
        super(CoordinateInputDialog, self).__init__(parent)
        self.x_coord = None
        self.y_coord = None
        self.setWindowTitle("Enter Coordinates")
        self.crs = crs
        layout = QVBoxLayout()
        if self.crs:
            crs_label = QLabel(f"Current CRS: {self.crs.authid()} - {self.crs.description()}")
            layout.addWidget(crs_label)
            note_label = QLabel("Note: Coordinates will be interpreted in the current project CRS.")
            note_label.setWordWrap(True)
            layout.addWidget(note_label)
        form_layout = QFormLayout()
        self.x_input = QLineEdit()
        self.y_input = QLineEdit()
        form_layout.addRow("X Coordinate:", self.x_input)
        form_layout.addRow("Y Coordinate:", self.y_input)
        layout.addLayout(form_layout)
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.validate_and_accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def validate_and_accept(self):
        try:
            self.x_coord = float(self.x_input.text())
            self.y_coord = float(self.y_input.text())
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric coordinates.")


class FlowlineModule:
    def __init__(self, iface):
        self.iface = iface
        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.selected_band_1 = 1
        self.selected_band_2 = 1
        self.coordinate = None
        self.map_tool = None
        self.backward_steps = False
        self.step_size = None
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None
        self.system = platform.system()
        self.miniconda_path = os.path.expanduser("~/miniconda3")
        self.conda_path = os.path.join(self.miniconda_path, "bin", "conda")
        if self.system in ["Linux", "Darwin"]:
            self.configure_environment()
        self.preset_manager = PresetManager(os.path.dirname(__file__))
        self.last_used_preset = None
        self.last_executed_command = None

    def show_download_popup(self, message="Downloading..."):
        self.progress_dialog = QProgressDialog(message, None, 0, 0, self.iface.mainWindow())
        self.progress_dialog.setWindowTitle("Please wait!")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.show()
        QApplication.processEvents()

    def hide_download_popup(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()

    def configure_environment(self):
        os.environ.pop("PYTHONHOME", None)
        os.environ["CONDA_PREFIX"] = self.miniconda_path
        miniconda_bin = f"{self.miniconda_path}/bin"
        current_path = os.environ.get("PATH", "")
        if miniconda_bin not in current_path.split(os.pathsep):
            os.environ["PATH"] = f"{miniconda_bin}:{current_path}"
            print(f"Updated System PATH: {os.environ['PATH']}")

    def save_current_settings(self):
        if not self.selected_raster_1 or not self.selected_raster_2:
            QMessageBox.warning(None, "Incomplete Preset", "Please select input rasters before saving preset.")
            return
        preset_data = {
            'raster_1_source': self.selected_raster_1.source(),
            'raster_1_name': self.selected_raster_1.name(),
            'raster_2_source': self.selected_raster_2.source(),
            'raster_2_name': self.selected_raster_2.name(),
            'band_1': self.selected_band_1,
            'band_2': self.selected_band_2,
            'backward_steps': self.backward_steps,
            'step_size': self.step_size,
            'max_integration_time': self.max_integration_time,
            'max_steps': self.max_steps,
            'output_format': self.output_format
        }
        dialog = SavePresetDialog(self.preset_manager, preset_data)
        dialog.exec_()

    def load_preset(self, preset_name):
        preset_data = self.preset_manager.get_preset(preset_name)
        if not preset_data:
            QMessageBox.warning(None, "Error", f"Could not load preset '{preset_name}'.")
            return False
        try:
            raster_1_source = preset_data.get('raster_1_source')
            raster_2_source = preset_data.get('raster_2_source')
            self.selected_raster_1 = QgsRasterLayer(raster_1_source, preset_data.get('raster_1_name'))
            self.selected_raster_2 = QgsRasterLayer(raster_2_source, preset_data.get('raster_2_name'))
            if not self.selected_raster_1.isValid() or not self.selected_raster_2.isValid():
                QMessageBox.warning(
                    None,
                    "Invalid Layers",
                    "Could not load raster layers from preset. The files may have moved or changed."
                )
                return False
            self.selected_band_1 = preset_data.get('band_1', 1)
            self.selected_band_2 = preset_data.get('band_2', 1)
            self.backward_steps = preset_data.get('backward_steps', False)
            self.step_size = preset_data.get('step_size')
            self.max_integration_time = preset_data.get('max_integration_time')
            self.max_steps = preset_data.get('max_steps')
            self.output_format = preset_data.get('output_format')
            self.last_used_preset = preset_name

            if self.system == "Windows":
                raster_path_1 = self.selected_raster_1.source()
                raster_path_2 = self.selected_raster_2.source()

                for prefix in ["NETCDF:", "HDF5:", "GRIB:"]:
                    if raster_path_1.startswith(prefix):
                        raster_path_1 = raster_path_1[len(prefix):].strip()
                    if raster_path_2.startswith(prefix):
                        raster_path_2 = raster_path_2[len(prefix):].strip()

                if ":" in raster_path_1:
                    file_path, variable = raster_path_1.rsplit(":", 1)
                    raster_path_1 = f"{file_path}?{variable}"
                if ":" in raster_path_2:
                    file_path, variable = raster_path_2.rsplit(":", 1)
                    raster_path_2 = f"{file_path}?{variable}"

                cmd = f'grd2stream "{raster_path_1}" "{raster_path_2}"'
                if self.backward_steps:
                    cmd += " -b"
                if self.step_size:
                    cmd += f" -d {self.step_size}"
                if self.max_integration_time:
                    cmd += f" -T {self.max_integration_time}"
                if self.max_steps:
                    cmd += f" -n {self.max_steps}"
                if self.output_format:
                    cmd += f" {self.output_format}"
                cmd += ' -f "<seed_file_path>"'
            else:
                gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
                grd2stream_path = os.path.join(gmt6_env_path, "bin", "grd2stream")
                raster_path_1 = self.selected_raster_1.source()
                raster_path_2 = self.selected_raster_2.source()

                for prefix in ["NETCDF:", "HDF5:", "GRIB:"]:
                    if raster_path_1.startswith(prefix):
                        raster_path_1 = raster_path_1[len(prefix):].strip()
                    if raster_path_2.startswith(prefix):
                        raster_path_2 = raster_path_2[len(prefix):].strip()

                if ":" in raster_path_1:
                    file_path, variable = raster_path_1.rsplit(":", 1)
                    raster_path_1 = f"{file_path}?{variable}"
                if ":" in raster_path_2:
                    file_path, variable = raster_path_2.rsplit(":", 1)
                    raster_path_2 = f"{file_path}?{variable}"

                cmd = f'"{self.conda_path}" run -n GMT6 "{grd2stream_path}" "{raster_path_1}" "{raster_path_2}"'
                if self.backward_steps:
                    cmd += " -b"
                if self.step_size:
                    cmd += f" -d {self.step_size}"
                if self.max_integration_time:
                    cmd += f" -T {self.max_integration_time}"
                if self.max_steps:
                    cmd += f" -n {self.max_steps}"
                if self.output_format:
                    cmd += f" {self.output_format}"
                cmd += ' -f "<seed_file_path>"'

            self.preset_command_template = cmd
            print(f"Preset Command Template: {cmd}")

            self.iface.messageBar().pushMessage(
                "Success",
                f"Preset '{preset_name}' loaded successfully. Choose how to select a coordinate.",
                level=Qgis.Info,
                duration=5
            )
            self.prompt_coordinate_input_method()
            return True
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Error loading preset: {str(e)}")
            return False

    def install_miniconda(self):
        if os.path.exists(self.conda_path):
            print("Miniconda is already installed!")
            return
        print("Installing Miniconda...")
        self.show_download_popup("Downloading & Installing Miniconda...")
        try:
            if self.system == "Windows":
                command = (
                    'curl -o miniconda.exe https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe && '
                    'miniconda.exe /S && '
                    'del miniconda.exe'
                )
                subprocess.run(["cmd", "/c", command], check=True)
            elif self.system in ["Linux", "Darwin"]:
                if self.system == "Linux":
                    url = "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
                elif self.system == "Darwin":
                    url = "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$(uname -m).sh"
                commands = [
                    f"mkdir -p {self.miniconda_path}",
                    f"curl -fsSL {url} -o {self.miniconda_path}/miniconda.sh",
                    f"bash {self.miniconda_path}/miniconda.sh -b -u -p {self.miniconda_path}",
                    f"rm {self.miniconda_path}/miniconda.sh"
                ]
                for cmd in commands:
                    subprocess.run(["bash", "-c", cmd], check=True)
            print("Miniconda is now installed!")
        except subprocess.CalledProcessError as e:
            print(f"Error during Miniconda installation: {e}")
        finally:
            self.hide_download_popup()

    def setup_conda_environment(self):
        self.install_miniconda()
        if not os.path.exists(self.conda_path):
            raise RuntimeError("Miniconda installation not found!")
        print("Setting up Conda environment...")
        self.show_download_popup("Setting up Conda environment & installing GMT6...")
        try:
            subprocess.run([self.conda_path, "config", "--add", "channels", "conda-forge"], check=True)
            subprocess.run([self.conda_path, "config", "--set", "channel_priority", "strict"], check=True)
            subprocess.run([self.conda_path, "create", "-y", "-n", "GMT6", "gmt=6*", "gdal", "hdf5", "netcdf4"], check=True)
            print("Conda environment 'GMT6' is now set up!")
        except subprocess.CalledProcessError as e:
            print(f"Error during GMT6 installation: {e}")
        finally:
            self.hide_download_popup()

    def install_grd2stream(self):
        plugin_root = os.path.dirname(__file__)
        gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
        grd2stream_executable = os.path.join(gmt6_env_path, "bin", "grd2stream")
        if self.system == "Windows":
            grd2stream_executable = os.path.join(plugin_root, "bin", "grd2stream")
        if os.path.exists(grd2stream_executable):
            print("grd2stream is already installed!")
            return
        print("Installing grd2stream...")
        self.show_download_popup("Building & Installing grd2stream...")
        # grd2stream-0.2.14
        # Copyright (c) 2013-2024, Thomas Kleiner
        # licensed under BSD-3-Clause License
        # see 'lib/LICENSE.txt' for full license text
        local_tar = os.path.join(plugin_root, "lib", "grd2stream-0.2.14.tar.gz")
        try:
            with tempfile.TemporaryDirectory() as build_dir:
                subprocess.run(
                    ["tar", "xvfz", local_tar],
                    cwd=build_dir,
                    check=True
                )
                grd2stream_dir = os.path.join(build_dir, "grd2stream-0.2.14")

                if self.system in ["Linux", "Darwin"]:
                    env = os.environ.copy()
                    env["LDFLAGS"] = "-Wl,-rpath,$CONDA_PREFIX/lib"
                    subprocess.run(
                        [self.conda_path, "run", "-n", "GMT6", "bash", "-c",
                         f'./configure --prefix="{gmt6_env_path}" --enable-gmt-api'],
                        cwd=grd2stream_dir,
                        env=env,
                        check=True
                    )
                    subprocess.run(
                        [self.conda_path, "run", "-n", "GMT6", "make"],
                        cwd=grd2stream_dir,
                        check=True
                    )
                    subprocess.run(
                        [self.conda_path, "run", "-n", "GMT6", "make", "install"],
                        cwd=grd2stream_dir,
                        check=True
                    )
                    # idk if stil needed
                    if self.system == "Darwin" and os.path.exists(grd2stream_executable):
                        rpath = os.path.join(gmt6_env_path, "lib")
                        subprocess.run(
                            ["install_name_tool", "-add_rpath", rpath, grd2stream_executable],
                            check=True
                        )

            print("Verifying grd2stream installation...")
            if os.path.exists(grd2stream_executable):
                print("grd2stream is now installed!")
            else:
                print("grd2stream installation failed!")
        except subprocess.CalledProcessError as e:
            print(f"Installation failed: {e}")
        finally:
            self.hide_download_popup()

    def is_gmt6_installed(self):
        if self.system == "Windows":
            return False
        else:
            gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
            return os.path.exists(gmt6_env_path)

    def prompt_missing_installation(self):
        if self.system == "Windows":
            QMessageBox.warning(
                None,
                "Windows Limitation",
                "Currently grd2stream is not accessible on Windows. You can still use the plugin to set up parameters and presets, but execution will only display the command that would be needed to calculate the flowline.",
                QMessageBox.Ok
            )
            return

        dialog = QDialog()
        dialog.setWindowTitle("Required Components")
        dialog.setMinimumWidth(250)
        layout = QVBoxLayout(dialog)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Select what to install:"))

        help_button = QPushButton(dialog)
        help_button.setIcon(QIcon(":/plugins/grd_2_stream/resources/icons/help.svg"))
        help_button.setToolTip("Help")
        help_button.setFixedSize(18, 18)
        from .help_widget import show_help
        help_button.clicked.connect(lambda: show_help(self.iface))
        header_layout.addWidget(help_button)

        layout.addLayout(header_layout)

        gmt6_checkbox = QCheckBox("Auto-Install GMT6 (via Miniconda)", dialog)
        grd2stream_checkbox = QCheckBox("Auto-Install grd2stream", dialog)
        gmt6_installed = self.is_gmt6_installed()
        if gmt6_installed:
            gmt6_checkbox.setEnabled(False)
            gmt6_checkbox.setChecked(True)
            grd2stream_checkbox.setEnabled(True)
        else:
            grd2stream_checkbox.setEnabled(False)

        def update_checkbox():
            grd2stream_checkbox.setEnabled(gmt6_checkbox.isChecked())

        gmt6_checkbox.stateChanged.connect(update_checkbox)
        install_button = QPushButton("Install", dialog)
        cancel_button = QPushButton("Cancel", dialog)
        layout.addWidget(gmt6_checkbox)
        layout.addWidget(grd2stream_checkbox)
        layout.addWidget(install_button)
        layout.addWidget(cancel_button)
        install_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            if not gmt6_installed and gmt6_checkbox.isChecked():
                self.setup_conda_environment()
            if grd2stream_checkbox.isChecked():
                self.install_grd2stream()

    def open_selection_dialog(self):
        if self.system == "Windows":
            QMessageBox.warning(
                None,
                "Windows Limitation",
                "Currently grd2stream is not accessible on Windows. You can still use the plugin to set up parameters and presets, but execution will only display the command that would be needed to calculate the flowline.",
                QMessageBox.Ok
            )
        else:
            gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
            grd2stream_executable = os.path.join(gmt6_env_path, "bin", "grd2stream")
            if not os.path.exists(grd2stream_executable):
                self.prompt_missing_installation()
                if not os.path.exists(grd2stream_executable):
                    return

        from .dialog_selection import SelectionDialog
        dialog = SelectionDialog(self.iface, self)

        if dialog.exec_():
            self.selected_raster_1 = dialog.selected_raster_1
            self.selected_raster_2 = dialog.selected_raster_2
            self.selected_band_1 = getattr(dialog, "selected_band_1", 1)
            self.selected_band_2 = getattr(dialog, "selected_band_2", 1)

            self.backward_steps = dialog.backward_steps
            self.step_size = dialog.step_size
            self.max_integration_time = dialog.max_integration_time
            self.max_steps = dialog.max_steps
            self.output_format = dialog.output_format

            self.last_used_preset = None

            self.iface.messageBar().pushMessage(
                "Info",
                f"Selected rasters: {self.selected_raster_1.name()}, {self.selected_raster_2.name()} (Bands: {self.selected_band_1}, {self.selected_band_2})",
                level=Qgis.Info,
                duration=5
            )
            self.prompt_coordinate_input_method()

    def use_last_settings(self):
        if self.selected_raster_1 and self.selected_raster_2:
            preset_data = {
                'raster_1_name': self.selected_raster_1.name(),
                'raster_2_name': self.selected_raster_2.name(),
                'band_1': self.selected_band_1,
                'band_2': self.selected_band_2,
                'backward_steps': self.backward_steps,
                'step_size': self.step_size,
                'max_steps': self.max_steps,
                'max_integration_time': self.max_integration_time,
                'output_format': self.output_format
            }
            return preset_data
        else:
            return None

    def prompt_coordinate_input_method(self):
        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle("Coordinate Selection Type")
        layout = QVBoxLayout(dialog)
        instruction = QLabel("Choose how to select a seed point for your flowline:")
        instruction.setWordWrap(True)
        layout.addWidget(instruction)
        method_group = QGroupBox()
        method_layout = QVBoxLayout(method_group)
        map_radio = QRadioButton("Click on the map")
        map_radio.setChecked(True)  # Default
        manual_radio = QRadioButton("Enter coordinates manually")
        method_layout.addWidget(map_radio)
        method_layout.addWidget(manual_radio)
        layout.addWidget(method_group)
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            if map_radio.isChecked():
                self.prompt_for_coordinate()
            else:
                self.prompt_for_manual_coordinate()

    def prompt_for_coordinate(self):
        if self.map_tool:
            try:
                self.map_tool.canvasClicked.disconnect(self.coordinate_selected)
            except Exception:
                pass
        self.map_tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.coordinate_selected)
        self.iface.mapCanvas().setMapTool(self.map_tool)
        self.iface.messageBar().pushMessage(
            "Info",
            "Click on the map to select a seed point for your flowline.",
            level=Qgis.Info,
            duration=5
        )

    def prompt_for_manual_coordinate(self):
        dialog = CoordinateInputDialog(self.iface.mainWindow(), self.iface.mapCanvas().mapSettings().destinationCrs())

        if dialog.exec_() == QDialog.Accepted:
            self.coordinate = (dialog.x_coord, dialog.y_coord)
            self.iface.messageBar().pushMessage(
                "Info",
                f"Coordinate entered manually: {self.coordinate}.",
                level=Qgis.Info,
                duration=5
            )
            self.run_grd2stream(verbose=True)

    def coordinate_selected(self, point):
        self.coordinate = (point.x(), point.y())
        self.iface.mapCanvas().unsetMapTool(self.map_tool)
        self.map_tool = None
        self.iface.messageBar().pushMessage(
            "Info",
            f"Coordinate selected: {self.coordinate}.",
            level=Qgis.Info,
            duration=5
        )
        self.run_grd2stream(verbose=True)

    def run_grd2stream(self, verbose=False):
        try:
            if not self.selected_raster_1 or not self.selected_raster_2:
                raise ValueError("Two raster layers must be selected.")
            if not self.coordinate:
                raise ValueError("A coordinate must be selected.")

            x, y = self.coordinate

            if self.system == "Windows":
                raster_path_1 = self.selected_raster_1.source()
                raster_path_2 = self.selected_raster_2.source()

                for prefix in ["NETCDF:", "HDF5:", "GRIB:"]:
                    if raster_path_1.startswith(prefix):
                        raster_path_1 = raster_path_1[len(prefix):].strip()
                    if raster_path_2.startswith(prefix):
                        raster_path_2 = raster_path_2[len(prefix):].strip()

                if ":" in raster_path_1:
                    file_path, variable = raster_path_1.rsplit(":", 1)
                    raster_path_1 = f"{file_path}?{variable}"
                if ":" in raster_path_2:
                    file_path, variable = raster_path_2.rsplit(":", 1)
                    raster_path_2 = f"{file_path}?{variable}"

                cmd = f'grd2stream "{raster_path_1}" "{raster_path_2}" -f "seed.txt"'
                if self.backward_steps:
                    cmd += " -b"
                if self.step_size:
                    cmd += f" -d {self.step_size}"
                if self.max_integration_time:
                    cmd += f" -T {self.max_integration_time}"
                if self.max_steps:
                    cmd += f" -n {self.max_steps}"
                if self.output_format:
                    cmd += f" {self.output_format}"

                self.last_executed_command = cmd
                print(f"Windows Command (not executed): {cmd}")
                print(f"Seed point coordinates: x={x}, y={y}")

                QMessageBox.information(
                    None,
                    "Command Information",
                    f"On Windows, grd2stream command execution is not available.\n\nThe command that would be executed is:\n\n{cmd}\n\nWith seed point at: x={x}, y={y}"
                )

                self.iface.messageBar().pushMessage(
                    "Info",
                    "Command displayed. No execution on Windows.",
                    level=Qgis.Info,
                    duration=5
                )
                return

            with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
                seed_file_path = temp_file.name
                temp_file.write(f"{x} {y}\n")

            raster_path_1 = self.selected_raster_1.source()
            raster_path_2 = self.selected_raster_2.source()

            for prefix in ["NETCDF:", "HDF5:", "GRIB:"]:
                if raster_path_1.startswith(prefix):
                    raster_path_1 = raster_path_1[len(prefix):].strip()
                if raster_path_2.startswith(prefix):
                    raster_path_2 = raster_path_2[len(prefix):].strip()

            if ":" in raster_path_1:
                file_path, variable = raster_path_1.rsplit(":", 1)
                raster_path_1 = f"{file_path}?{variable}"
            if ":" in raster_path_2:
                file_path, variable = raster_path_2.rsplit(":", 1)
                raster_path_2 = f"{file_path}?{variable}"

            if hasattr(self, 'preset_command_template') and self.preset_command_template is not None:
                cmd = self.preset_command_template.replace('<seed_file_path>', seed_file_path)
            else:
                gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
                grd2stream_path = os.path.join(gmt6_env_path, "bin", "grd2stream")

                cmd = f'"{self.conda_path}" run -n GMT6 "{grd2stream_path}" "{raster_path_1}" "{raster_path_2}" -f "{seed_file_path}"'
                if self.backward_steps:
                    cmd += " -b"
                if self.step_size:
                    cmd += f" -d {self.step_size}"
                if self.max_integration_time:
                    cmd += f" -T {self.max_integration_time}"
                if self.max_steps:
                    cmd += f" -n {self.max_steps}"
                if self.output_format:
                    cmd += f" {self.output_format}"

            self.last_executed_command = cmd
            print(f"Executing Command: {cmd}")

            result = subprocess.run(
                ["bash", "-c", cmd],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            if result.returncode != 0:
                print(f"Command failed with error: {result.stderr}")
                print(f"Command output: {result.stdout}")
                raise RuntimeError(f"Command failed: {result.stderr}")

            if verbose or result.returncode == 0:
                print("Raw Output:\n", result.stdout)

            self.load_streamline_from_output(result.stdout)

            self.iface.messageBar().pushMessage(
                "Success",
                "grd2stream executed. Results loaded as a layer.",
                level=Qgis.Info,
                duration=5
            )

        except Exception as e:
            print(f"Error in run_grd2stream: {e}")
            self.iface.messageBar().pushMessage(
                "Error", f"Unexpected error: {e}", level=Qgis.Critical, duration=5
            )
        finally:
            if self.system != "Windows" and 'seed_file_path' in locals() and seed_file_path:
                try:
                    os.unlink(seed_file_path)
                except Exception as e:
                    print(f"Error during cleanup: {e}")

    def load_streamline_from_output(self, output):
        """Parses grd2stream output and loads it as a vector layer in QGIS."""
        if self.system == "Windows":
            return

        try:
            features = []

            format_fields = {
                None: ["x", "y", "dist"],
                "-l": ["x", "y", "dist", "v_x", "v_y"],
                "-t": ["x", "y", "dist", "v_x", "v_y", "time"]
            }
            field_names = format_fields.get(self.output_format, ["x", "y", "dist"])

            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(">"):
                    continue

                parts = list(map(float, line.split()))
                if len(parts) < len(field_names):
                    continue

                x, y = parts[:2]
                attributes = parts

                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                feature.setAttributes(attributes)
                features.append(feature)

            field_types = ["double"] * len(field_names)
            uri_fields = "&".join(f"field={name}:{ftype}" for name, ftype in zip(field_names, field_types))
            uri = f"point?crs={QgsProject.instance().crs().authid()}&{uri_fields}"

            layer_name = "Streamline"
            layer = QgsVectorLayer(uri, layer_name, "memory")
            provider = layer.dataProvider()
            provider.addFeatures(features)

            if not layer.isValid():
                raise RuntimeError("Failed to load output as a vector layer.")

            QgsProject.instance().addMapLayer(layer)

            self.iface.messageBar().pushMessage(
                "Success", f"Layer '{layer_name}' successfully loaded.", level=Qgis.Info, duration=5
            )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"Failed to load output as layer: {e}", level=Qgis.Critical, duration=5
            )
