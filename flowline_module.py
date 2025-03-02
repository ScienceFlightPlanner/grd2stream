import os
import platform
import subprocess
import tempfile

from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QCheckBox, QMessageBox, QProgressDialog, QApplication)
from PyQt5.QtCore import Qt

from .preset_manager import PresetManager, PresetDialog, SavePresetDialog

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
        if self.system in ["Linux", "Darwin"]:
            self.conda_path = os.path.join(self.miniconda_path, "bin", "conda")
        else:
            self.conda_path = os.path.join(self.miniconda_path, "Scripts", "conda.exe")
        self.configure_environment()
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.preset_manager = PresetManager(plugin_dir)
        self.last_used_preset = None

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
        os.environ["PATH"] = f"{self.miniconda_path}/bin:" + os.environ["PATH"]
        print(f"Updated System PATH: {os.environ['PATH']}")
        print(f"Using Conda from: {self.conda_path}")

    def save_current_settings(self):
        if not self.selected_raster_1 or not self.selected_raster_2:
            QMessageBox.warning(None,"Incomplete Preset","Please select input rasters before saving preset.")
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

    def manage_presets(self):
        dialog = PresetDialog(self.preset_manager)
        if dialog.exec_() == QDialog.Accepted:
            preset_name = getattr(dialog, 'selected_preset', None)
            if preset_name:
                self.load_preset(preset_name)

    def load_preset(self, preset_name):
        preset_data = self.preset_manager.get_preset(preset_name)
        if not preset_data:
            QMessageBox.warning(None, "Error", f"Could not load preset '{preset_name}'.")
            return False
        try:
            raster_1_source = preset_data.get('raster_1_source')
            raster_2_source = preset_data.get('raster_2_source')
            if not os.path.exists(raster_1_source.split('?')[0]) or not os.path.exists(raster_2_source.split('?')[0]):
                QMessageBox.warning(
                    None,
                    "Missing Files",
                    "One or both of the raster files in this preset no longer exist at the specified location."
                )
                return False
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
            self.iface.messageBar().pushMessage(
                "Success",
                f"Preset '{preset_name}' loaded successfully. Click on the map to select a coordinate.",
                level=Qgis.Info,
                duration=5
            )
            self.prompt_for_coordinate()
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
        gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
        prefix = gmt6_env_path
        grd2stream_executable = os.path.join(gmt6_env_path, "bin", "grd2stream")
        if self.system == "Windows":
            grd2stream_executable += ".exe"
        if os.path.exists(grd2stream_executable):
            print("grd2stream is already installed!")
            return
        print("Installing grd2stream...")
        self.show_download_popup("Building & Installing grd2stream...")
        plugin_root = os.path.dirname(__file__)
        # grd2stream-0.2.14
        # Copyright (c) 2013-2024, Thomas Kleiner
        # licensed under BSD-3-Clause License
        # see 'libs/LICENSE.txt' for full license text
        local_tar = os.path.join(plugin_root, "libs/grd2stream-0.2.14.tar.gz")
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
                         f'./configure --prefix="{prefix}" --enable-gmt-api'],
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
                elif self.system == "Windows":
                    conda_init = (
                        "$env:Path = \"$env:USERPROFILE\\miniconda3\\Scripts;"
                        "$env:USERPROFILE\\miniconda3\\Library\\bin;$env:Path\"; "
                        "conda activate GMT6"
                    )
                    build_commands = (
                        f"{conda_init}; cd \"{grd2stream_dir}\"; "
                        f'./configure --prefix="{prefix}" --enable-gmt-api; '
                        "make; make install"
                    )
                    subprocess.run(
                        ["powershell", "-Command", build_commands],
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
        gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
        return os.path.exists(gmt6_env_path)

    def prompt_missing_installation(self):
        dialog = QDialog()
        dialog.setWindowTitle("Installation Required")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Some components required for grd2stream are missing.\nSelect what to install:"))
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
        dialog.setLayout(layout)
        if dialog.exec_() == QDialog.Accepted:
            if not gmt6_installed and gmt6_checkbox.isChecked():
                self.setup_conda_environment()
            if grd2stream_checkbox.isChecked():
                self.install_grd2stream()

    def open_selection_dialog(self):

        gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
        grd2stream_executable = os.path.join(gmt6_env_path, "bin", "grd2stream")
        if self.system == "Windows":
            grd2stream_executable += ".exe"
        if not os.path.exists(grd2stream_executable):
            self.prompt_missing_installation()

        from .selection_dialog import SelectionDialog
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
            self.prompt_for_coordinate()

    def use_last_settings(self):
        if self.last_used_preset:
            return self.load_preset(self.last_used_preset)
        elif self.selected_raster_1 and self.selected_raster_2:
            self.iface.messageBar().pushMessage(
                "Info",
                f"Using last settings. Selected rasters: {self.selected_raster_1.name()}, {self.selected_raster_2.name()}"
                f" (Bands: {self.selected_band_1}, {self.selected_band_2})",
                level=Qgis.Info,
                duration=5
            )
            self.prompt_for_coordinate()
            return True
        else:
            QMessageBox.information(None,"No Previous Settings",
                                    "No previous settings found. Please select input parameters.")
            return self.open_selection_dialog()

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
        self.run_grd2stream()

    def run_grd2stream(self):
        try:
            try:
                gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
                grd2stream_executable = os.path.join(gmt6_env_path, "bin", "grd2stream")
                if self.system == "Windows":
                    grd2stream_executable += ".exe"
                while not os.path.exists(grd2stream_executable):
                    self.prompt_missing_installation()
                    if not os.path.exists(grd2stream_executable):
                        reply = QMessageBox.question(
                            None, "Installation Required",
                            "grd2stream is not installed! Would you like to retry?",
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                        )
                        if reply == QMessageBox.No:
                            self.iface.messageBar().pushMessage(
                                "Error",
                                "grd2stream installation was canceled...",
                                level=Qgis.Critical,
                                duration=5
                            )
                            return
            except Exception as e:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Unexpected error: {e}",
                    level=Qgis.Critical,
                    duration=5
                )

            if not self.selected_raster_1 or not self.selected_raster_2:
                raise ValueError("Two raster layers must be selected.")
            if not self.coordinate:
                raise ValueError("A coordinate must be selected.")

            x, y = self.coordinate
            with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
                seed_file_path = temp_file.name
                temp_file.write(f"{x} {y}\n")

            gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
            grd2stream_path = os.path.join(gmt6_env_path, "bin", "grd2stream")

            raster_path_1 = self.selected_raster_1.source()
            raster_path_2 = self.selected_raster_2.source()

            for prefix in ["NETCDF:", "HDF5:", "GRIB:"]:  # Extend this list if needed
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

            print(f"Executing Command: {cmd}")
            result = subprocess.run(
                ["bash", "-c", cmd],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")

            print("Raw Output:\n", result.stdout)
            self.load_streamline_from_output(result.stdout)

            self.iface.messageBar().pushMessage(
                "Success",
                "grd2stream executed. Results loaded as a layer.",
                level=Qgis.Info,
                duration=5
            )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"Unexpected error: {e}", level=Qgis.Critical, duration=5
            )

    def load_streamline_from_output(self, output):
        """Parses grd2stream output and loads it as a vector layer in QGIS."""
        try:
            features = []

            format_fields = {
                None: ["longitude", "latitude", "dist"],
                "-l": ["longitude", "latitude", "dist", "v_x", "v_y"],
                "-t": ["longitude", "latitude", "dist", "v_x", "v_y", "time"]
            }
            field_names = format_fields.get(self.output_format, ["longitude", "latitude", "dist"])

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
