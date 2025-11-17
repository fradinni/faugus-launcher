# Python Imports
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')

import sys
import importlib.util
from pathlib import Path

# Imports from app
import faugus_launcher as Launcher


#
# Global variables
#
loaded_plugins = []

#
# Load all plugins from the user's plugin directory.
#
def load_plugins():
    # Get the plugins directory path
    plugins_dir = Path.home() / '.local/share/faugus-launcher/plugins'
    
    # Create the plugins directory if it doesn't exist
    plugins_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if the directory exists and is accessible
    if not plugins_dir.exists() or not plugins_dir.is_dir():
        print(f'Plugins directory not found: {plugins_dir}')
        return

    # Iterate through each subdirectory in the plugins directory
    for plugin_path in plugins_dir.iterdir():
        if plugin_path.name != "example_plugin" and plugin_path.is_dir():
            # Look for a plugin.py file in the plugin directory
            plugin_file = plugin_path / 'plugin.py'
            
            if plugin_file.exists() and plugin_file.is_file():
                try:
                    # Load the plugin module dynamically
                    plugin_name = plugin_path.name
                    spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                    
                    if spec and spec.loader:
                        plugin_module = importlib.util.module_from_spec(spec)
                        sys.modules[plugin_name] = plugin_module
                        spec.loader.exec_module(plugin_module)
                        
                        # Call the plugin's initialize function if it exists
                        if hasattr(plugin_module, 'initialize'):
                            plugin_module.initialize()
                            loaded_plugins.append(plugin_module)
                            print(f'✓ Plugin loaded: {plugin_name}')
                        else:
                            print(f'Plugin {plugin_name} has no initialize() function')
                    else:
                        print(f'Failed to load plugin spec: {plugin_name}')
                        
                except Exception as e:
                    print(f'Error loading plugin {plugin_path.name}: {e}')
            else:
                print(f'No plugin.py found in {plugin_path.name}')

#
# Method called when the application is initialized.
#
def initialize():
    load_plugins()

#
# Method called when the Main window is built.
# At this point, the main window and its components are initialized.
# This function also calls the main_window_hook in all loaded plugins.
#
def main_window_hook(main_window: Launcher.Main):
    # Call main_window_hook in all loaded plugins
    for plugin in loaded_plugins:
        if hasattr(plugin, 'main_window_hook'):
            try:
                plugin.main_window_hook(main_window)
            except Exception as e:
                print(f'Error calling main_window_hook in plugin {plugin.__name__}: {e}')

#
# Method called when the Settings window is built.
# At this point, the settings window and its components are initialized.
# This function also calls the settings_window_hook in all loaded plugins.
#
def settings_window_hook(settings_window: Launcher.Settings):
    # Call settings_window_hook in all loaded plugins
    for plugin in loaded_plugins:
        if hasattr(plugin, 'settings_window_hook'):
            try:
                plugin.settings_window_hook(settings_window)
            except Exception as e:
                print(f'Error calling settings_window_hook in plugin {plugin.__name__}: {e}')