import os
from qgis.PyQt.QtWidgets import QDockWidget, QWidget, QVBoxLayout
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import QtWidgets

_current_help_widget = None


class HelpWidget(QDockWidget):
    """
    A dockable widget that displays the plugin's help manual.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setMinimumWidth(400)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        self.text_browser = QtWidgets.QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        self.load_help_content()
        layout.addWidget(self.text_browser)
        self.setWidget(content_widget)
        self.setFeatures(QDockWidget.DockWidgetClosable)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self)

    def load_help_content(self):
        """Load the HTML help manual content from resources."""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            with open(os.path.join(plugin_dir, "resources", "manual.html"), 'r', encoding='utf-8') as f:
                self.text_browser.setHtml(f.read())
        except Exception as e:
            self.text_browser.setHtml(f"<h1>Error loading Help Manual...</h1><p>{str(e)}</p>")


def show_help(iface):
    """Show or hide the help widget."""
    global _current_help_widget
    if _current_help_widget is None or not _current_help_widget.isVisible():
        _current_help_widget = HelpWidget(iface)
        _current_help_widget.show()
    else:
        _current_help_widget.close()
        _current_help_widget = None


def add_help_menu_action(iface, plugin_dir):
    """Add a help action to the QGIS help menu"""
    from qgis.PyQt.QtWidgets import QAction
    from qgis.PyQt.QtGui import QIcon
    help_action = QAction(
        QIcon(os.path.join(plugin_dir, "icon.png")),
        "grd2stream - Help Manual",
        iface.mainWindow()
    )
    help_action.triggered.connect(lambda: show_help(iface))
    iface.pluginHelpMenu().addAction(help_action)
    return help_action
