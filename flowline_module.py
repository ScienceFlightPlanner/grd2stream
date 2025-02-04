import os
import platform
import subprocess
import tempfile
import sys

from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QDoubleSpinBox, QMessageBox

class FlowlineModule:
    def __init__(self, iface):
        self.iface = iface
        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.coordinate = None
        self.map_tool = None
        self.backward_steps = False
        self.step_size = 200.0
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None
        self.dialog = QDialog()
        self.gmt6_checkbox = QCheckBox("Install GMT6 (via Miniconda)")
        self.grd2stream_checkbox = QCheckBox("Install grd2stream")
        self.grd2stream_checkbox.setEnabled(False)
        self.system = platform.system()
        self.miniconda_path = os.path.expanduser("~/miniconda3")
        if self.system in ["Linux", "Darwin"]:
            self.conda_path = os.path.join(self.miniconda_path, "bin", "conda")
        else:
            self.conda_path = os.path.join(self.miniconda_path, "Scripts", "conda.exe")
        self.configure_environment()

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
        if self.system == "Windows":
            command = (
                "wget \"https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe\" -outfile \".\\miniconda.exe\"; "
                "Start-Process -FilePath \".\\miniconda.exe\" -ArgumentList \"/S\" -Wait; "
                "del .\\miniconda.exe"
            )
            subprocess.run(["powershell", "-Command", command], check=True)
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

    def setup_conda_environment(self):
        self.install_miniconda()
        if not os.path.exists(self.conda_path):
            raise RuntimeError("Miniconda installation not found!")
        print("Setting up Conda environment...")
        if self.system in ["Linux", "Darwin"]:
            try:
                subprocess.run([self.conda_path, "config", "--add", "channels", "conda-forge"], check=True)
                subprocess.run([self.conda_path, "config", "--set", "channel_priority", "strict"], check=True)
                subprocess.run([self.conda_path, "create", "-y", "-n", "GMT6", "gmt=6*", "gdal", "hdf5", "netcdf4"], check=True)
                print("Conda environment 'GMT6' is now set up!")
            except subprocess.CalledProcessError as e:
                print(f"Error setting up Conda environment: {e}")
        elif self.system == "Windows":
            conda_commands = (
                "$env:Path = \"$env:USERPROFILE\\miniconda3\\Scripts;$env:USERPROFILE\\miniconda3\\Library\\bin;$env:Path\"; "
                "conda init powershell; "
                "conda config --add channels conda-forge; "
                "conda config --set channel_priority strict; "
                "conda create -y -n GMT6 gmt=6* gdal hdf5 netcdf4"
            )
            subprocess.run(["powershell", "-Command", conda_commands], check=True)
        print("Conda environment is now set up!")

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
        plugin_root = os.path.dirname(__file__)
        local_tar = os.path.join(plugin_root, "grd2stream-0.2.14.tar.gz")
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

    def prompt_missing_installation(self):
        self.dialog.setWindowTitle("Installation Required")
        layout = QVBoxLayout()
        label = QLabel("Some components required for grd2stream are missing.\nSelect what to install:")
        layout.addWidget(label)
        self.gmt6_checkbox = QCheckBox("Install GMT6 (via Miniconda)", self.dialog)
        self.grd2stream_checkbox = QCheckBox("Install grd2stream", self.dialog)
        self.grd2stream_checkbox.setEnabled(False)
        layout.addWidget(self.gmt6_checkbox)
        layout.addWidget(self.grd2stream_checkbox)
        self.gmt6_checkbox.stateChanged.connect(self.update_grd2stream_checkbox)
        ok_button = QPushButton("Install", self.dialog)
        cancel_button = QPushButton("Cancel", self.dialog)
        layout.addWidget(ok_button)
        layout.addWidget(cancel_button)
        self.dialog.setLayout(layout)
        ok_button.clicked.connect(self.dialog.accept)
        cancel_button.clicked.connect(self.dialog.reject)
        if self.dialog.exec_() == QDialog.Accepted:
            if self.gmt6_checkbox.isChecked():
                self.setup_conda_environment()
            if self.grd2stream_checkbox.isChecked():
                self.install_grd2stream()

    def update_grd2stream_checkbox(self):
        if self.gmt6_checkbox.isChecked():
            self.grd2stream_checkbox.setEnabled(True)
        else:
            self.grd2stream_checkbox.setChecked(False)
            self.grd2stream_checkbox.setEnabled(False)

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

            self.backward_steps = dialog.backward_steps
            self.step_size = dialog.step_size
            self.max_integration_time = dialog.max_integration_time
            self.max_steps = dialog.max_steps
            self.output_format = dialog.output_format

            self.iface.messageBar().pushMessage(
                "Info",
                f"Selected rasters: {self.selected_raster_1.name()}, {self.selected_raster_2.name()}",
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
            gmt6_env_path = os.path.join(self.miniconda_path, "envs", "GMT6")
            grd2stream_executable = os.path.join(gmt6_env_path, "bin", "grd2stream")
            if self.system == "Windows":
                grd2stream_executable += ".exe"
            if not os.path.exists(grd2stream_executable):
                self.prompt_missing_installation()
            if not os.path.exists(grd2stream_executable):
                self.iface.messageBar().pushMessage(
                    "Error",
                    "grd2stream is not installed!",
                    level=Qgis.Critical,
                    duration=5
                )
                return

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

            raster_path_1 = self.selected_raster_1.dataProvider().dataSourceUri()
            raster_path_2 = self.selected_raster_2.dataProvider().dataSourceUri()

            cmd = f'{self.conda_path} run -n GMT6 {grd2stream_path} {raster_path_1} {raster_path_2} -f {seed_file_path}'
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
        self.step_size = 0.0  # Default step size
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

        layout.addWidget(QLabel("Options:"))

        self.backward_checkbox = QCheckBox("Backward Steps (-b)")
        layout.addWidget(self.backward_checkbox)

        self.step_size_input = QDoubleSpinBox()
        self.step_size_input.setDecimals(2)
        self.step_size_input.setMinimum(0.0)
        self.step_size_input.setMaximum(float("inf"))
        self.step_size_input.setSingleStep(1.0)
        self.step_size_input.setValue(0.0)
        layout.addWidget(QLabel("Step Size (-d):"))
        layout.addWidget(self.step_size_input)

        self.max_time_input = QLineEdit()
        self.max_time_input.setPlaceholderText("Maximum Integration Time (default: none)")
        layout.addWidget(QLabel("Maximum Integration Time (-T):"))
        layout.addWidget(self.max_time_input)

        self.max_steps_input = QLineEdit()
        self.max_steps_input.setPlaceholderText("Maximum Number of Steps (default: 10000)")
        layout.addWidget(QLabel("Maximum Number of Steps (-n):"))
        layout.addWidget(self.max_steps_input)

        layout.addWidget(QLabel("Output Format:"))
        self.output_format_box = QComboBox()
        self.output_format_box.addItem("x y dist (default)", None)
        self.output_format_box.addItem("x y dist v_x v_y (-l)", "-l")
        self.output_format_box.addItem("x y dist v_x v_y time (-t)", "-t")
        layout.addWidget(self.output_format_box)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def populate_layers(self):
        layers = QgsProject.instance().mapLayers().values()
        raster_layers = [layer for layer in layers if isinstance(layer, QgsRasterLayer)]
        for layer in raster_layers:
            self.layer_box_1.addItem(layer.name(), layer)
            self.layer_box_2.addItem(layer.name(), layer)

    def accept(self):
        index_1 = self.layer_box_1.currentIndex()
        index_2 = self.layer_box_2.currentIndex()

        self.selected_raster_1 = self.layer_box_1.itemData(index_1)
        self.selected_raster_2 = self.layer_box_2.itemData(index_2)

        if self.selected_raster_1 == self.selected_raster_2:
            self.iface.messageBar().pushMessage(
                "Error",
                "Please select two different grid layers.",
                level=Qgis.Critical,
                duration=5
            )
            return

        self.backward_steps = self.backward_checkbox.isChecked()
        self.step_size = self.step_size_input.value()
        self.max_integration_time = self.max_time_input.text() or None
        self.max_steps = self.max_steps_input.text() or None
        self.output_format = self.output_format_box.currentData()

        super().accept()
