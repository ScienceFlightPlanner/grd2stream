# grd2stream
The `grd2stream` QGIS plugin allows to comfortably **generate multiple flowlines from velocity grids** by selecting seed points. This plugin utilizes **GMT6** to ensure compatibility with all GDAL file formats!

---

## Platform Support
> The plugin installs GMT6 in an isolated Conda environment, which **<u>does not</u> affect any existing native GMT6 installations** on your system

### macOS & Linux
- ✅ Fully supported

### Windows
- 🚧 Coming Soon! Currently under development...

---

## Troubleshooting
- For detailed logs, check the QGIS Python console!

---

## Authors
- [**Thomas Kleiner**](https://github.com/tkleiner)
- [**ScienceFlightPlanner**](https://github.com/ScienceFlightPlanner)

---

## Third-Party Licenses
>This plugin includes the following third-party components:
- [**grd2stream**](https://github.com/tkleiner/grd2stream) (by [Thomas Kleiner](https://github.com/tkleiner)):
   - CLI tool that calculates stream lines from gridded velocity fields using Runge-Kutta integration methods
   - licensed under the BSD 3-Clause License
     - see the full [LICENSE](lib/LICENSE.txt) text for details
