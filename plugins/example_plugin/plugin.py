"""
Example Plugin for Faugus Launcher

This is a simple example plugin that demonstrates how to create
a plugin for Faugus Launcher. It simply prints a message to the console
when initialized.
"""
import os
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, GdkPixbuf

PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))

def initialize():
    """
    This function is called when the plugin is loaded.
    It's the entry point for the plugin.
    """
    print("=" * 50)
    print("Example Plugin Loaded Successfully!")
    print("This is a demonstration of the plugin system.")
    print("=" * 50)

def main_window_hook(main_window):
    """
    This function is called when the main window is built.
    Plugins can use this to add UI elements or modify the main window.
    """
    print("Example Plugin: main_window_hook called!")

def settings_window_hook(settings_window):
    """
    This function is called when the settings window is built.
    Plugins can use this to add UI elements or modify the settings window.
    """
    print('settings_window_hook')
    pass
