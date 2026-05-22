"""Whisper Wayland - Key Mapping

Key code mapping and hotkey parsing functionality for evdev integration.
"""

import logging
import typing

try:
    import evdev
except ImportError as e:
    raise ImportError(
        "evdev is required for key monitoring. Install with: pip install evdev or uv add evdev"
    ) from e

_logger = logging.getLogger(__name__)


class KeyMappingError(Exception):
    """Raised when key mapping operations fail."""

    pass


class KeyMapping:
    """Handles key code mapping and hotkey parsing for evdev integration."""

    def __init__(self) -> None:
        """Initialize key mapping."""
        self._key_map = self._build_key_map()

    def _build_key_map(self) -> dict[int, str]:
        """Build mapping from evdev keycodes to key names."""
        key_map = {
            evdev.ecodes.KEY_LEFTCTRL: "ctrl",
            evdev.ecodes.KEY_RIGHTCTRL: "rightctrl",
            evdev.ecodes.KEY_LEFTALT: "alt",
            evdev.ecodes.KEY_RIGHTALT: "altgr",
            evdev.ecodes.KEY_LEFTSHIFT: "shift",
            evdev.ecodes.KEY_RIGHTSHIFT: "shift",
            evdev.ecodes.KEY_SPACE: "space",
            evdev.ecodes.KEY_ENTER: "enter",
            evdev.ecodes.KEY_ESC: "esc",
            evdev.ecodes.KEY_TAB: "tab",
            evdev.ecodes.KEY_BACKSPACE: "backspace",
            evdev.ecodes.KEY_DELETE: "delete",
            evdev.ecodes.KEY_INSERT: "insert",
            evdev.ecodes.KEY_PAGEDOWN: "pagedown",
            evdev.ecodes.KEY_SCROLLLOCK: "scrolllock",
            evdev.ecodes.KEY_COMPOSE: "compose",  # The compose key
            evdev.ecodes.KEY_MENU: "menu",
            evdev.ecodes.BTN_LEFT: "mouse_left",
            evdev.ecodes.BTN_RIGHT: "mouse_right",
            evdev.ecodes.BTN_MIDDLE: "mouse_middle",
            evdev.ecodes.BTN_SIDE: "mouse_side",
            evdev.ecodes.BTN_EXTRA: "mouse_extra",
            evdev.ecodes.BTN_FORWARD: "mouse_forward",
            evdev.ecodes.BTN_BACK: "mouse_back",
            evdev.ecodes.BTN_TASK: "mouse_task",
            # Function keys
            evdev.ecodes.KEY_F1: "f1",
            evdev.ecodes.KEY_F2: "f2",
            evdev.ecodes.KEY_F3: "f3",
            evdev.ecodes.KEY_F4: "f4",
            evdev.ecodes.KEY_F5: "f5",
            evdev.ecodes.KEY_F6: "f6",
            evdev.ecodes.KEY_F7: "f7",
            evdev.ecodes.KEY_F8: "f8",
            evdev.ecodes.KEY_F9: "f9",
            evdev.ecodes.KEY_F10: "f10",
            evdev.ecodes.KEY_F11: "f11",
            evdev.ecodes.KEY_F12: "f12",
        }

        # Add letter keys (keyboard layout order, not alphabetical)
        letter_keys = {
            evdev.ecodes.KEY_A: "a",
            evdev.ecodes.KEY_B: "b",
            evdev.ecodes.KEY_C: "c",
            evdev.ecodes.KEY_D: "d",
            evdev.ecodes.KEY_E: "e",
            evdev.ecodes.KEY_F: "f",
            evdev.ecodes.KEY_G: "g",
            evdev.ecodes.KEY_H: "h",
            evdev.ecodes.KEY_I: "i",
            evdev.ecodes.KEY_J: "j",
            evdev.ecodes.KEY_K: "k",
            evdev.ecodes.KEY_L: "l",
            evdev.ecodes.KEY_M: "m",
            evdev.ecodes.KEY_N: "n",
            evdev.ecodes.KEY_O: "o",
            evdev.ecodes.KEY_P: "p",
            evdev.ecodes.KEY_Q: "q",
            evdev.ecodes.KEY_R: "r",
            evdev.ecodes.KEY_S: "s",
            evdev.ecodes.KEY_T: "t",
            evdev.ecodes.KEY_U: "u",
            evdev.ecodes.KEY_V: "v",
            evdev.ecodes.KEY_W: "w",
            evdev.ecodes.KEY_X: "x",
            evdev.ecodes.KEY_Y: "y",
            evdev.ecodes.KEY_Z: "z",
        }
        key_map.update(letter_keys)

        # Add number keys
        for i in range(10):
            key_map[evdev.ecodes.KEY_1 + i] = str(i + 1)
        key_map[evdev.ecodes.KEY_0] = "0"

        return key_map

    def parse_hotkey_combination(self, hotkey_str: str) -> set[str]:
        """Parse hotkey string into key set for detection.

        Args:
            hotkey_str: Hotkey configuration string

        Returns:
            Set of key names in the hotkey combination

        Raises:
            KeyMappingError: If hotkey format is invalid
        """
        hotkey_normalized = hotkey_str.lower().strip()
        if not hotkey_normalized:
            raise KeyMappingError("Hotkey cannot be empty")

        # Map common key names
        key_mapping = {
            "ctrl": "ctrl",
            "control": "ctrl",
            "rightctrl": "rightctrl",
            "right_ctrl": "rightctrl",
            "rctrl": "rightctrl",
            "rightcontrol": "rightctrl",
            "right_control": "rightctrl",
            "alt": "alt",
            "altgr": "altgr",
            "alt_gr": "altgr",
            "rightalt": "altgr",
            "right_alt": "altgr",
            "ralt": "altgr",
            "shift": "shift",
            "space": "space",
            "enter": "enter",
            "return": "enter",
            "tab": "tab",
            "esc": "esc",
            "escape": "esc",
            "insert": "insert",
            "ins": "insert",
            "pagedown": "pagedown",
            "page_down": "pagedown",
            "pgdn": "pagedown",
            "scrolllock": "scrolllock",
            "scroll_lock": "scrolllock",
            "screenlock": "scrolllock",
            "screen_lock": "scrolllock",
            "compose": "compose",
            "menu": "menu",
            "mouse_left": "mouse_left",
            "leftmouse": "mouse_left",
            "left_mouse": "mouse_left",
            "leftclick": "mouse_left",
            "left_click": "mouse_left",
            "mouse1": "mouse_left",
            "mouse_right": "mouse_right",
            "rightmouse": "mouse_right",
            "right_mouse": "mouse_right",
            "rightclick": "mouse_right",
            "right_click": "mouse_right",
            "mouse2": "mouse_right",
            "mouse_middle": "mouse_middle",
            "middlemouse": "mouse_middle",
            "middle_mouse": "mouse_middle",
            "middleclick": "mouse_middle",
            "middle_click": "mouse_middle",
            "mouse3": "mouse_middle",
            "mouse_side": "mouse_side",
            "side_mouse": "mouse_side",
            "sidebutton": "mouse_side",
            "side_button": "mouse_side",
            "mouse4": "mouse_side",
            "mouse_extra": "mouse_extra",
            "extra_mouse": "mouse_extra",
            "extrabutton": "mouse_extra",
            "extra_button": "mouse_extra",
            "mouse5": "mouse_extra",
            "mouse_back": "mouse_back",
            "back_mouse": "mouse_back",
            "backbutton": "mouse_back",
            "back_button": "mouse_back",
            "mouse_forward": "mouse_forward",
            "forward_mouse": "mouse_forward",
            "forwardbutton": "mouse_forward",
            "forward_button": "mouse_forward",
            "mouse_task": "mouse_task",
            "task_mouse": "mouse_task",
            "taskbutton": "mouse_task",
            "task_button": "mouse_task",
        }

        # Handle single key (like "compose")
        if "+" not in hotkey_normalized:
            return {key_mapping.get(hotkey_normalized, hotkey_normalized)}

        # Split by '+' and normalize key names
        key_parts = [part.strip() for part in hotkey_normalized.split("+")]
        if not key_parts:
            raise KeyMappingError(f"Invalid hotkey format: {hotkey_str}")

        hotkey_combination: set[str] = set()
        for part in key_parts:
            if part in key_mapping:
                hotkey_combination.add(key_mapping[part])
            elif len(part) == 1 and part.isalnum():
                # Single character keys
                hotkey_combination.add(part)
            elif part.startswith("f") and part[1:].isdigit():
                # Function keys like f1, f2, etc.
                hotkey_combination.add(part)
            else:
                _logger.warning(f"Unknown key in hotkey: {part}")
                hotkey_combination.add(part)

        _logger.debug(f"Parsed hotkey combination: {hotkey_combination}")
        return hotkey_combination

    def get_key_name(self, keycode: int) -> typing.Optional[str]:
        """Convert keycode to readable key name.

        Args:
            keycode: evdev keycode

        Returns:
            Key name string or None if not recognized
        """
        if keycode in self._key_map:
            return self._key_map[keycode]

        # Try to get key name from evdev
        try:
            key_val = evdev.ecodes.KEY[keycode]

            # Handle different types that evdev might return
            raw_key_name: typing.Any = None
            if isinstance(key_val, tuple) and key_val:
                raw_key_name = key_val[0]
            else:
                raw_key_name = key_val

            # Convert to string regardless of whether it's bytes or str
            if isinstance(raw_key_name, bytes):
                key_name_str = raw_key_name.decode()
            elif isinstance(raw_key_name, str):
                key_name_str = raw_key_name
            else:
                return None

            # Remove KEY_ prefix if present
            if key_name_str.startswith("KEY_"):
                return key_name_str[4:].lower()
            else:
                return key_name_str.lower()

        except (KeyError, UnicodeDecodeError, AttributeError):
            pass

        return None

    def get_key_aliases(self, key_name: str) -> set[str]:
        """Return generic aliases for side-specific modifier keys."""
        aliases = {
            "rightctrl": {"ctrl"},
            "altgr": {"alt"},
        }
        return aliases.get(key_name, set())

    @staticmethod
    def new() -> "KeyMapping":
        """Create key mapping instance.

        Returns:
            KeyMapping instance
        """
        return KeyMapping()
