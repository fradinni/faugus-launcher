import json
import os
import gettext

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

_ = gettext.gettext

PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'ankergames_settings.json')


class AnkerGamesSettingsDialog(Gtk.Dialog):
    """Per-game settings dialog to set the AnkerGames game URL and installed version.

    Backward-compatible JSON schema (stored in CONFIG_FILE):
    - Legacy format: { "Game Title": "https://ankergames.net/g/some-game" }
    - New format: {
          "Game Title": {
              "url": "https://ankergames.net/game/some-game",
              "installed_version": "1.2.3"
          }
      }
    """

    def __init__(self, parent=None, game_title: str | None = None, game_id: str | int | None = None):
        super().__init__(title=_("AnkerGames Settings"), parent=parent, modal=True)
        self.set_default_size(520, 160)
        self.set_transient_for(parent)
        self.set_destroy_with_parent(True)

        self.game_title = game_title or ""
        # Persist the optional game_id so we can propose a default URL when none is saved
        self.game_id = str(game_id) if game_id is not None else None
        self._config = self._load_config()

        # Content area
        box = self.get_content_area()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_border_width(12)
        box.add(content)

        # Game title (read-only)
        h_title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_title = Gtk.Label(label=_("Game:"))
        lbl_title.set_xalign(0)
        self.entry_title = Gtk.Entry()
        self.entry_title.set_text(self.game_title)
        self.entry_title.set_editable(False)
        h_title.pack_start(lbl_title, False, False, 0)
        h_title.pack_start(self.entry_title, True, True, 0)

        # Game URL
        h_url = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_url = Gtk.Label(label=_("AnkerGames URL:"))
        lbl_url.set_xalign(0)
        self.entry_url = Gtk.Entry()
        self.entry_url.set_placeholder_text("https://ankergames.net/game/...")
        self.entry_url.set_activates_default(True)
        h_url.pack_start(lbl_url, False, False, 0)
        h_url.pack_start(self.entry_url, True, True, 0)

        # Installed Version
        h_version = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_version = Gtk.Label(label=_("Installed Version:"))
        lbl_version.set_xalign(0)
        self.entry_version = Gtk.Entry()
        self.entry_version.set_placeholder_text("e.g. V 1.2.3")
        self.entry_version.set_activates_default(True)
        h_version.pack_start(lbl_version, False, False, 0)
        h_version.pack_start(self.entry_version, True, True, 0)

        content.pack_start(h_title, False, False, 0)
        content.pack_start(h_url, False, False, 0)
        content.pack_start(h_version, False, False, 0)

        # Dialog buttons
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        # Add a Reset button to restore the URL to the default value (based on game_id)
        reset_button = self.add_button(_("Reset"), Gtk.ResponseType.APPLY)
        ok_button = self.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        ok_button.grab_default()

        # Hook reset button
        reset_button.connect("clicked", self._on_reset_clicked)
        # Prevent the dialog from closing when clicking Reset (ResponseType.APPLY)
        # by intercepting the dialog's response signal.
        self.connect("response", self._on_dialog_response)

        # Prefill from config. If no user-defined URL is saved, propose a default based on game_id
        current_url = ""
        current_version = ""
        if self.game_title and self.game_title in self._config:
            val = self._config.get(self.game_title)
            if isinstance(val, str):
                current_url = val
            elif isinstance(val, dict):
                current_url = val.get("url", "") or ""
                current_version = val.get("installed_version", "") or ""

        if current_url:
            self.entry_url.set_text(current_url)
        else:
            # No saved URL; suggest default (may be empty if no game_id)
            self.entry_url.set_text(self._compute_default_url())

        if current_version:
            self.entry_version.set_text(current_version)

        # Validate on change
        self.entry_url.connect("changed", self._on_url_changed, ok_button)
        self._on_url_changed(self.entry_url, ok_button)  # initial state

        self.show_all()

    def _on_url_changed(self, entry: Gtk.Entry, ok_button: Gtk.Button):
        text = entry.get_text().strip()
        # Minimal validation: allow empty or URLs starting with http(s)
        valid = (text == "") or text.startswith("http://") or text.startswith("https://")
        ok_button.set_sensitive(valid)

    def _compute_default_url(self) -> str:
        """Return the default URL to use for this game, or empty if unknown."""
        if self.game_id:
            return f"https://ankergames.net/game/{self.game_id}"
        return ""

    def _on_reset_clicked(self, button: Gtk.Button):
        """Reset the URL entry to the default value without saving immediately."""
        self.entry_url.set_text(self._compute_default_url())
        # Keep focus on the URL entry for convenience
        self.entry_url.grab_focus()

    def _on_dialog_response(self, dialog: Gtk.Dialog, response_id: int):
        """Intercept the APPLY response to keep the dialog open on Reset."""
        if response_id == Gtk.ResponseType.APPLY:
            # Perform reset action and stop the response so run() doesn't return
            self._on_reset_clicked(None)
            # Stop emission of the response signal so the dialog stays open
            try:
                # PyGObject provides stop_emission_by_name
                self.stop_emission_by_name("response")
            except Exception:
                # Fallback for environments where emit_stop_by_name is available
                try:
                    self.emit_stop_by_name("response")
                except Exception:
                    pass

    def run(self):
        response = super().run()
        if response == Gtk.ResponseType.OK:
            self._save()
        return response

    def _load_config(self) -> dict:
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_config(self, data: dict):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Show a simple error dialog if saving fails
            md = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=_("Failed to save AnkerGames settings."),
            )
            md.format_secondary_text(str(e))
            md.run()
            md.destroy()

    def _save(self):
        if not self.game_title:
            return
        url = self.entry_url.get_text().strip()
        installed_version = self.entry_version.get_text().strip()

        if url or installed_version:
            # Save in new object format
            self._config[self.game_title] = {
                "url": url,
                "installed_version": installed_version,
            }
        else:
            # Remove entry if both fields are empty
            if self.game_title in self._config:
                del self._config[self.game_title]
        self._save_config(self._config)
