import os
import platform
import subprocess
import tempfile
import sys

from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QDoubleSpinBox, QMessageBox, QProgressDialog, QApplication
from PyQt5.QtCore import Qt

class FlowlineModule:
    def __init__(self, iface):
        self.iface = iface
        self.selected_raster_1 = None
        self.selected_raster_2 = None
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

        dialog = SelectionDialog(self.iface)

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

            self.iface.messageBar().pushMessage(
                "Info",
                f"Selected rasters: {self.selected_raster_1.name()}, {self.selected_raster_2.name()} (Bands: {self.selected_band_1}, {self.selected_band_2})",
                level=Qgis.Info,
                duration=5
            )
            self.prompt_for_coordinate()

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
            "Click on the map to select a coordinate for the grd2stream command.",
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
                self.iface.messageBar().pushMessage(
                    "Success",
                    "grd2stream is installed!",
                    level=Qgis.Info,
                    duration=5
                )
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

class SelectionDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
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

        layout.addWidget(QLabel("Select the 1st grid layer:"))
        self.layer_box_1 = QComboBox()
        layout.addWidget(self.layer_box_1)
        layout.addWidget(QLabel("Select the 2nd grid layer:"))
        self.layer_box_2 = QComboBox()
        layout.addWidget(self.layer_box_2)

        self.populate_layers()

        self.backward_checkbox = QCheckBox("Backward Steps (yes/no)")
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
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

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
