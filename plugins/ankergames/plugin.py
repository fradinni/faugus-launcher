"""
AnkerGames Plugin for Faugus Launcher

Provides an "AnkerGames: Settings" context menu entry per game to set the
AnkerGames game URL. The URL is stored in a JSON file beside this plugin and
loaded when the settings window opens.
"""
import os
import webbrowser
import gettext
import importlib.util
import json as _json

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import threading
import time

# Dynamically load sibling settings.py because the plugin is loaded as a
# standalone module (not as a package), so relative imports won't work.
_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'settings.py')
_spec = importlib.util.spec_from_file_location('ankergames_settings', _SETTINGS_PATH)
anker_settings = importlib.util.module_from_spec(_spec) if _spec and _spec.loader else None
if _spec and _spec.loader and anker_settings is not None:
    _spec.loader.exec_module(anker_settings)
else:
    anker_settings = None

# Dynamically load scrapper.py (same reasoning as settings.py)
_SCRAPPER_PATH = os.path.join(os.path.dirname(__file__), 'scrapper.py')
_spec_scr = importlib.util.spec_from_file_location('ankergames_scrapper', _SCRAPPER_PATH)
scrapper = importlib.util.module_from_spec(_spec_scr) if _spec_scr and _spec_scr.loader else None
if _spec_scr and _spec_scr.loader and scrapper is not None:
    _spec_scr.loader.exec_module(scrapper)
else:
    scrapper = None

# Translation helper
_ = gettext.gettext

PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
ANKERGAMES_URL = "https://ankergames.net/"

# Keep a reference to the main window so we can access selection and parent
_MAIN_WINDOW = None

# Track CSS provider installation for the update badge
_BADGE_CSS_INSTALLED = False

def _ensure_update_badge_css() -> None:
    """Install CSS to style the update badge as a green pill and ready badge as gray.

    Uses widget name selectors: label#ankergames_update_badge and label#ankergames_ready_badge
    """
    global _BADGE_CSS_INSTALLED
    if _BADGE_CSS_INSTALLED:
        return
    css = b"""
    label#ankergames_update_badge {
        padding: 2px 8px;
        border-width: 1px;
        border-style: solid;
        border-color: #22c55e; /* green-600 */
        border-radius: 5px; /* pill */
        color: #22c55e;
        background-color: transparent;
        font-weight: 600;
    }
    label#ankergames_ready_badge {
        padding: 2px 8px;
        border-width: 1px;
        border-style: solid;
        border-color: #6b7280; /* gray-500 */
        border-radius: 5px; /* pill */
        color: #6b7280;
        background-color: transparent;
        font-weight: 600;
    }
    """
    try:
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            _BADGE_CSS_INSTALLED = True
    except Exception:
        # If CSS load fails, we just proceed without special styling
        _BADGE_CSS_INSTALLED = True

def initialize() -> None:
    """
    This function is called when the plugin is loaded.
    It's the entry point for the plugin.
    """
    # Nothing to initialize for now

def main_window_hook(main_window):
    """
    This function is called when the main window is built.
    Plugins can use this to add UI elements or modify the main window.
    """
    global _MAIN_WINDOW
    _MAIN_WINDOW = main_window
    # Create top bar
    top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    top_bar_padding = 25 if main_window.interface_mode == "Banners" else 10
    top_bar.set_margin_top(10)
    top_bar.set_margin_left(top_bar_padding)
    top_bar.set_margin_right(top_bar_padding)
    # Add AnkerGames Button
    top_bar.add(get_ankergames_button())
    # Add top bar to main window
    main_window.box_main.pack_start(top_bar, False, True, 0)
    main_window.box_main.reorder_child(top_bar, 0)
    # Show top bar elements
    top_bar.show_all()

    # Ensure CSS for the pill badge is available
    _ensure_update_badge_css()

    # Do NOT check updates on selection changes per requirements.

    # Kick off an asynchronous background scan on startup to check updates
    # for games that have an installed version set.
    try:
        t = threading.Thread(target=_background_startup_scan, args=(), daemon=True)
        t.start()
    except Exception:
        pass

    # Context Menu Entries
    # Insert a separator to visually isolate AnkerGames entries from original ones
    separator = Gtk.SeparatorMenuItem()
    main_window.context_menu.append(separator)
    separator.show_all()

    # Create AnkerGames parent menu with children
    ankergames_menu_item = get_ankergames_parent_menu()
    main_window.context_menu.append(ankergames_menu_item)
    ankergames_menu_item.show_all()

def settings_window_hook(settings_window):
    # This plugin currently has no global app settings
    return

def get_ankergames_button():
    button_anker = Gtk.Button.new_with_label("  AnkerGames")
    button_anker.set_can_focus(False)
    button_anker.set_tooltip_text("Open AnkerGames Store")
    button_anker.set_image(load_icon(f"{PLUGIN_DIR}/ankergames.png"))
    button_anker.set_image_position(Gtk.PositionType.LEFT)
    button_anker.connect("clicked", lambda b: webbrowser.open(ANKERGAMES_URL))
    return button_anker

def get_context_menu_entry() -> Gtk.MenuItem:
    menu_item_ankergames = Gtk.MenuItem(label=_("AnkerGames: Settings"))
    menu_item_ankergames.connect("activate", on_context_menu_click)
    return menu_item_ankergames

def get_game_page_menu_entry() -> Gtk.MenuItem:
    menu_item_game_page = Gtk.MenuItem(label=_("AnkerGames: Game Page"))
    menu_item_game_page.connect("activate", on_context_menu_open_game_page)
    return menu_item_game_page

class AnkerGamesDynamicMenuItem(Gtk.MenuItem):
    """Custom menu item that dynamically builds its submenu based on selected game configuration."""
    
    def __init__(self, label="AnkerGames"):
        super().__init__(label=label)
        self.connect("select", self._on_select)
    
    def _on_select(self, menu_item):
        """Rebuild the submenu when the parent menu item is selected."""
        # Remove existing submenu if any
        current_submenu = self.get_submenu()
        if current_submenu:
            current_submenu.destroy()
        
        # Create new submenu with current game configuration
        submenu = Gtk.Menu()
        
        # Always add Settings child
        settings_item = Gtk.MenuItem(label=_("Settings"))
        settings_item.connect("activate", on_context_menu_click)
        submenu.append(settings_item)
        
        # Check if selected game is configured (has both URL and installed version)
        is_game_configured = _is_current_game_configured()
        
        # Only add Game Page and Check Updates if game is configured
        if is_game_configured:
            # Add Game Page child
            game_page_item = Gtk.MenuItem(label=_("Game Page"))
            game_page_item.connect("activate", on_context_menu_open_game_page)
            submenu.append(game_page_item)
            
            # Add Check Updates child
            check_updates_item = Gtk.MenuItem(label=_("Check Updates"))
            check_updates_item.connect("activate", on_context_menu_check_update)
            submenu.append(check_updates_item)
        
        # Show all items and set the submenu
        submenu.show_all()
        self.set_submenu(submenu)

def get_ankergames_parent_menu() -> Gtk.MenuItem:
    """Create AnkerGames parent menu with conditional children visibility.
    
    Game Page and Check Updates are only shown when the selected game
    has both URL and installed version configured.
    """
    return AnkerGamesDynamicMenuItem("AnkerGames")

def _is_current_game_configured() -> bool:
    """Check if the currently selected game has both URL and installed version configured."""
    if _MAIN_WINDOW is None:
        return False
    
    # Get current selection from the flowbox
    selected_children = _MAIN_WINDOW.flowbox.get_selected_children()
    if not selected_children:
        return False
    
    selected_child = selected_children[0]
    hbox = selected_child.get_child()
    try:
        game_label = hbox.get_children()[1]
        title = game_label.get_text()
    except Exception:
        title = getattr(_MAIN_WINDOW, 'current_title', None)
    
    if not title:
        return False
    
    # Try to resolve the game_id
    game_id = None
    try:
        if hasattr(_MAIN_WINDOW, 'games'):
            game = next((g for g in _MAIN_WINDOW.games if getattr(g, 'title', None) == title), None)
            if game is not None and hasattr(game, 'gameid'):
                game_id = getattr(game, 'gameid')
    except Exception:
        game_id = None
    
    # Check if game has both URL and installed version configured
    url, installed = _get_game_settings(title, game_id)
    return bool(url and installed)

def load_icon(path: str, size: int = 24) -> Gtk.Image:
    return Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size))

def on_context_menu_click(menu_item):
    """Open the AnkerGames settings dialog for the currently selected game."""
    if _MAIN_WINDOW is None:
        return
    if anker_settings is None or not hasattr(anker_settings, 'AnkerGamesSettingsDialog'):
        return
    # Get current selection from the flowbox
    selected_children = _MAIN_WINDOW.flowbox.get_selected_children()
    if not selected_children:
        return
    selected_child = selected_children[0]
    # The child content is an HBox where the second child is a label with the title
    hbox = selected_child.get_child()
    try:
        game_label = hbox.get_children()[1]
        title = game_label.get_text()
    except Exception:
        title = getattr(_MAIN_WINDOW, 'current_title', None)
    # Try to resolve the game_id from the main window's games list
    game_id = None
    try:
        if title and hasattr(_MAIN_WINDOW, 'games'):
            game = next((g for g in _MAIN_WINDOW.games if getattr(g, 'title', None) == title), None)
            if game is not None and hasattr(game, 'gameid'):
                game_id = getattr(game, 'gameid')
    except Exception:
        game_id = None
    # Open dialog
    dialog = anker_settings.AnkerGamesSettingsDialog(parent=_MAIN_WINDOW, game_title=title, game_id=game_id)
    dialog.run()
    dialog.destroy()
    # Per requirement, do not auto-check after saving settings.

def on_context_menu_open_game_page(menu_item):
    """Open the AnkerGames game page for the currently selected game.

    Priority:
    1) If a user-defined URL exists in the plugin settings JSON, open it.
    2) Else, if we can resolve a game_id, open https://ankergames.net/game/<game_id>
    3) Fallback to the AnkerGames home page.
    """
    if _MAIN_WINDOW is None:
        return
    # Get current selection from the flowbox
    selected_children = _MAIN_WINDOW.flowbox.get_selected_children()
    if not selected_children:
        webbrowser.open(ANKERGAMES_URL)
        return
    selected_child = selected_children[0]
    hbox = selected_child.get_child()
    try:
        game_label = hbox.get_children()[1]
        title = game_label.get_text()
    except Exception:
        title = getattr(_MAIN_WINDOW, 'current_title', None)

    # Try to resolve the game_id
    game_id = None
    try:
        if title and hasattr(_MAIN_WINDOW, 'games'):
            game = next((g for g in _MAIN_WINDOW.games if getattr(g, 'title', None) == title), None)
            if game is not None and hasattr(game, 'gameid'):
                game_id = getattr(game, 'gameid')
    except Exception:
        game_id = None

    # Try load user-defined URL from JSON config
    settings_path = os.path.join(PLUGIN_DIR, 'ankergames_settings.json')
    url = None
    try:
        if title and os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            if isinstance(data, dict):
                candidate = data.get(title, None)
                if isinstance(candidate, str) and candidate.strip():
                    url = candidate.strip()
                elif isinstance(candidate, dict):
                    cand_url = candidate.get('url', '') if candidate else ''
                    if isinstance(cand_url, str) and cand_url.strip():
                        url = cand_url.strip()
    except Exception:
        url = None

    # Build fallback URL if needed
    if not url and game_id is not None:
        url = f"https://ankergames.net/game/{game_id}"

    # Final fallback to home page
    if not url:
        url = ANKERGAMES_URL

    webbrowser.open(url)


def on_context_menu_check_update(menu_item):
    """Manually trigger update check asynchronously for the selected game.

    Skips fetching when no installed version is set.
    """
    if _MAIN_WINDOW is None or scrapper is None:
        return
    # Get current selection
    selected_children = _MAIN_WINDOW.flowbox.get_selected_children()
    if not selected_children:
        return
    selected_child = selected_children[0]
    hbox = selected_child.get_child()
    try:
        game_label = hbox.get_children()[1]
        title = game_label.get_text()
    except Exception:
        title = getattr(_MAIN_WINDOW, 'current_title', None)

    # resolve game_id
    game_id = None
    try:
        if title and hasattr(_MAIN_WINDOW, 'games'):
            game = next((g for g in _MAIN_WINDOW.games if getattr(g, 'title', None) == title), None)
            if game is not None and hasattr(game, 'gameid'):
                game_id = getattr(game, 'gameid')
    except Exception:
        game_id = None

    # Run check in background thread
    def _work():
        url, installed = _get_game_settings(title, game_id)
        
        # Check if game has AnkerGames settings configured (both url and installed version)
        is_configured = bool(url and installed)
        
        if not installed:
            # No installed version set; ensure any badge is removed and exit
            GLib.idle_add(_apply_badge_result, title, False, "", is_configured)
            return
        if not url:
            GLib.idle_add(_apply_badge_result, title, False, "", is_configured)
            return
        latest = ""
        try:
            latest = scrapper.get_latest_version(url)
        except Exception:
            latest = ""
        if not latest:
            GLib.idle_add(_apply_badge_result, title, False, "", is_configured)
            return
        needs_update = False
        try:
            needs_update = scrapper.compare_versions(installed, latest) < 0
        except Exception:
            needs_update = (installed.strip() != latest.strip())
        GLib.idle_add(_apply_badge_result, title, needs_update, latest, is_configured)

    try:
        threading.Thread(target=_work, daemon=True).start()
    except Exception:
        pass


# ----- Helpers -----
def _load_config_dict() -> dict:
    settings_path = os.path.join(PLUGIN_DIR, 'ankergames_settings.json')
    if not os.path.exists(settings_path):
        return {}
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_game_settings(title: str, game_id) -> tuple[str, str]:
    """Return (url, installed_version) for a title, supporting legacy JSON.

    If no URL in settings, compute default using game_id when available.
    """
    data = _load_config_dict()
    url = ""
    installed = ""
    if title and data:
        val = data.get(title)
        if isinstance(val, str):
            url = val.strip()
        elif isinstance(val, dict):
            url = (val.get('url', '') or '').strip()
            installed = (val.get('installed_version', '') or '').strip()

    if not url and game_id is not None:
        url = f"https://ankergames.net/game/{game_id}"
    return url, installed


def _find_hbox_for_title(title: str):
    """Find the FlowBox child hbox whose label text matches title."""
    try:
        for child in _MAIN_WINDOW.flowbox.get_children():
            hbox = child.get_child()
            try:
                game_label = hbox.get_children()[1]
                t = game_label.get_text()
            except Exception:
                t = None
            if t == title:
                return hbox
    except Exception:
        pass
    return None


def _find_title_label_in_hbox(hbox: Gtk.Box):
    """Return the title label presumed to be the second child, else None."""
    try:
        return hbox.get_children()[1]
    except Exception:
        return None


def _get_widget_name(widget) -> str:
    try:
        return widget.get_name() or ""
    except Exception:
        return getattr(widget, 'name', '') or ""


def _set_widget_name(widget, name: str) -> None:
    try:
        widget.set_name(name)
    except Exception:
        try:
            setattr(widget, 'name', name)
        except Exception:
            pass


def _ensure_title_container(hbox: Gtk.Box):
    """Ensure the title label lives inside a vertical box so we can place the
    update badge under the title. Returns (title_box, title_label).

    Structure after ensuring:
    hbox children: [icon/cover?, title_box, ...]
    title_box (Gtk.Box VERTICAL, name='ankergames_title_box') children:
      - title_label (existing)
      - optional badge label (name='ankergames_update_badge')
    """
    # Try to get current second child (expected title or container)
    children = hbox.get_children()
    if len(children) < 2:
        return None, None
    second = children[1]
    # If it's already our container, try to find the title label
    if isinstance(second, Gtk.Box) and _get_widget_name(second) == 'ankergames_title_box':
        title_box = second
        # Title should be the first child
        title_label = None
        try:
            if title_box.get_children():
                c0 = title_box.get_children()[0]
                if isinstance(c0, Gtk.Label):
                    title_label = c0
        except Exception:
            title_label = None
        return title_box, title_label

    # Otherwise, the second child is expected to be the title label itself
    title_label = second if isinstance(second, Gtk.Label) else None
    if title_label is None:
        return None, None

    # Keep packing properties of the title label in the hbox
    try:
        expand, fill, padding, pack_type = hbox.query_child_packing(title_label)
    except Exception:
        expand, fill, padding, pack_type = (True, True, 0, Gtk.PackType.START)

    # Remove the label from hbox and create the vertical title box
    hbox.remove(title_label)
    title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    _set_widget_name(title_box, 'ankergames_title_box')
    # Re-pack the title_box with the same properties
    hbox.pack_start(title_box, expand, fill, padding)
    try:
        hbox.reorder_child(title_box, 1)
    except Exception:
        pass

    # Put the title label inside the title_box as the first child
    try:
        # Left-align the title label to match original look
        title_label.set_xalign(0.0)
    except Exception:
        pass
    title_box.pack_start(title_label, False, False, 0)
    title_box.show_all()
    return title_box, title_label


def _remove_existing_badge(hbox: Gtk.Box):
    """Remove any existing update or ready badge from either the hbox (legacy placement)
    or from the inner title container, if present."""
    # First, legacy: direct children on hbox
    for child in list(hbox.get_children()):
        if isinstance(child, Gtk.Label):
            widget_name = _get_widget_name(child)
            if widget_name in ['ankergames_update_badge', 'ankergames_ready_badge']:
                hbox.remove(child)
                # do not break; there should be only one but be safe
    # Then, look for our title container
    children = hbox.get_children()
    if len(children) >= 2:
        maybe_box = children[1]
        if isinstance(maybe_box, Gtk.Box) and _get_widget_name(maybe_box) == 'ankergames_title_box':
            for child in list(maybe_box.get_children()):
                if isinstance(child, Gtk.Label):
                    widget_name = _get_widget_name(child)
                    if widget_name in ['ankergames_update_badge', 'ankergames_ready_badge']:
                        maybe_box.remove(child)
                        # only one badge is expected
                        break


def _make_badge(text: str, badge_type: str = 'update') -> Gtk.Label:
    lbl = Gtk.Label(label=text)
    # Name to help identify later
    if badge_type == 'ready':
        _set_widget_name(lbl, 'ankergames_ready_badge')
        lbl.set_tooltip_text(_("AnkerGames: Game is ready to play"))
    else:
        _set_widget_name(lbl, 'ankergames_update_badge')
        lbl.set_tooltip_text(_("AnkerGames: A newer version is available"))
    # Visuals for inline placement next to the title
    try:
        lbl.set_xalign(0.0)
    except Exception:
        pass
    # No top margin for inline placement
    try:
        lbl.set_margin_top(0)
    except Exception:
        pass
    # Add a small left margin so the pill does not stick to the title text
    try:
        lbl.set_margin_left(6)
    except Exception:
        pass
    return lbl


def _apply_badge_result(title: str, needs_update: bool, latest: str, is_configured: bool = False):
    """Apply badge UI update for a given title on the main thread.
    
    Args:
        title: Game title
        needs_update: Whether an update is needed (show "New version" badge)
        latest: Latest version string (not used for display, just for compatibility)
        is_configured: Whether the game has AnkerGames settings configured
    """
    if _MAIN_WINDOW is None or not title:
        return False
    hbox = _find_hbox_for_title(title)
    if hbox is None:
        return False
    _remove_existing_badge(hbox)
    
    if needs_update:
        # Show a simple pill that reads "Update"
        badge = _make_badge(_("New version"), 'update')
        badge.set_margin_top(15)
        badge.set_margin_bottom(15)
        badge.set_margin_right(15)
        badge.set_margin_left(15)
        badge.set_xalign(0.5)
        # Place badge inline next to the title (legacy placement)
        hbox.pack_end(badge, False, True, 0)
        hbox.show_all()
    elif is_configured and not needs_update:
        # Show "Ready" badge for configured games that are up to date
        badge = _make_badge(_("Ready"), 'ready')
        badge.set_margin_top(15)
        badge.set_margin_bottom(15)
        badge.set_margin_right(15)
        badge.set_margin_left(15)
        badge.set_xalign(0.5)
        hbox.pack_end(badge, False, True, 0)
        hbox.show_all()
    # No badge for games that don't have AnkerGames settings configured
    
    return False  # remove idle source


def _background_startup_scan():
    """Scan all games on startup asynchronously and update badges for those
    with an installed_version set. Network work runs here; UI updates via idle_add.
    """
    if _MAIN_WINDOW is None or scrapper is None:
        return
    games = []
    try:
        if hasattr(_MAIN_WINDOW, 'games'):
            games = list(_MAIN_WINDOW.games)
    except Exception:
        games = []
    for game in games:
        try:
            title = getattr(game, 'title', None)
            game_id = getattr(game, 'gameid', None)
            if not title:
                continue
            url, installed = _get_game_settings(title, game_id)
            
            # Check if game has AnkerGames settings configured (both url and installed version)
            is_configured = bool(url and installed)
            
            if not installed:
                # skip fetching if installed version not set
                GLib.idle_add(_apply_badge_result, title, False, "", is_configured)
                continue
            if not url:
                GLib.idle_add(_apply_badge_result, title, False, "", is_configured)
                continue
            latest = scrapper.get_latest_version(url)
            if not latest:
                GLib.idle_add(_apply_badge_result, title, False, "", is_configured)
                continue
            try:
                needs_update = scrapper.compare_versions(installed, latest) < 0
            except Exception:
                needs_update = (installed.strip() != latest.strip())
            GLib.idle_add(_apply_badge_result, title, needs_update, latest, is_configured)
            time.sleep(0.2)  # light throttling between requests
        except Exception:
            # ignore errors for individual games
            continue
