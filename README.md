# grd2stream – a QGIS Plugin

**Generate streamlines from gridded datasets**

![grd2stream logo](icon.png)

The [`grd2stream`](https://scienceflightplanner.github.io/grd2stream/) QGIS plugin allows you to comfortably generate multiple flowlines from gridded datasets by selecting seed points. This plugin utilizes [GMT6](https://www.generic-mapping-tools.org/) to ensure compatibility with all GDAL file formats!

## 🌟 Features

- Generate streamlines using Runge-Kutta integration from any GDAL-compatible rasters
- Interactive seed point selection via map clicks or manual coordinate entry
- Configurable integration parameters (step size, max steps, etc.)
- Save & load parameter presets for repeated workflows
- Isolated Conda environment that doesn't interfere with existing GMT installations

## 🖥️ Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS    | ✅ Fully supported | Automatic dependency installation |
| Linux    | ✅ Fully supported | Automatic dependency installation |
| Windows  | 🚧 Coming Soon | Currently allows parameter configuration only |

> The plugin installs GMT6 in an isolated Conda environment, which **does not** affect any existing native GMT6 installations on your system!

## 📋 Prerequisites

- QGIS 3.4 or higher
- Internet connection for initial dependency installation
- ~500 MB disk space for Conda environment (if dependencies need to be installed)

## 🔧 Installation

### From QGIS Plugin Repository

1. Open QGIS
2. Navigate to Plugins → Manage and Install Plugins
3. Search for "grd2stream"
4. Click "Install Plugin"

### Manual Installation

1. Download the latest release zip file
2. Open QGIS
3. Navigate to Plugins → Manage and Install Plugins → Install from ZIP
4. Select the downloaded zip file
5. Click "Install Plugin"

## 🚀 Quick Start

1. Click the grd2stream icon in the QGIS toolbar
2. If this is your first run, allow the plugin to install required dependencies (Linux/macOS only)
3. Select two raster layers:
   - First raster: X component data
   - Second raster: Y component data
4. Configure parameters or load a saved preset
5. Choose a method to select the seed point (map click or manual coordinates)
6. The plugin will calculate the flowline & add it as a vector layer to your project

## ⚙️ Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| Backward Steps | Trace flowline in both directions | Off |
| Step Size | Distance increment for integration | min(x_inc, y_inc) / 5 |
| Max Integration Time | Maximum time for integration process | Unlimited |
| Max Steps | Maximum number of steps to calculate | 10,000 |
| Output Format | Data columns in output layer | x y dist |

## 🧰 Working with Presets

Save time by storing your parameter configurations:

- **Save Preset**: After configuring parameters, click "Save as Preset"
- **Load Preset**: Click "Load Preset" to use a saved configuration
- **Last Settings**: Quickly reapply the last used configuration

## ❓ Troubleshooting

- **No flowline appears**: Ensure seed point was not placed in an area with undefined values
- **Missing dependencies**: Allow the plugin to install required components when prompted
- **Unexpected results**: Verify that both input rasters have the same extent, resolution, and coordinate system

For detailed logs, check the QGIS Python console!

## 🔄 How It Works

The plugin:
1. Reads data from two input rasters (X and Y components)
2. Uses GMT6's grd2stream utility to perform Runge-Kutta integration
3. Traces streamline starting from chosen seed point
4. Converts the output to a QGIS vector layer

### Contributing

Contributions are welcome! Priority areas include:
- Windows support implementation

## 📜 License

- **Plugin**: GNU General Public License v3.0 (GPL-3.0)
- [**grd2stream CLI tool**](https://github.com/tkleiner/grd2stream): BSD 3-Clause License (see [lib/LICENSE.txt](lib/LICENSE.txt))

## 👥 Authors

- [**Thomas Kleiner**](https://github.com/tkleiner)
- [**ScienceFlightPlanner**](https://github.com/ScienceFlightPlanner)
