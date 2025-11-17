# Example Plugin for Faugus Launcher

This is a simple example plugin that demonstrates the plugin system for Faugus Launcher.

## Structure

- `plugin.py` - Main plugin file with the `initialize()` function

## What it does

When loaded, this plugin simply prints a message to the console to demonstrate that the plugin system is working correctly.

## Creating Your Own Plugin

1. Create a new directory in `~/.local/share/faugus-launcher/plugins/your_plugin_name/`
2. Create a `plugin.py` file in that directory
3. Implement an `initialize()` function that will be called when the plugin loads
4. You can access the Faugus Launcher modules and components from your plugin

## Example

```python
def initialize():
    print("My plugin is loaded!")
    # Your plugin code here
```
