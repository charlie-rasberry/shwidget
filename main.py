import subprocess
from pynput import keyboard
import threading
from PIL import Image
from pystray import Icon as TrayIcon, MenuItem as TrayMenuItem
import sys  # Added for resource_path
import os   # Added for resource_path

# --- Function to get the correct path for resources (like icon.png) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not bundled, or _MEIPASS not set (e.g. running as script)
        # Use the directory of the current script file
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- Load Configuration ---
try:
    # This will work when running as a script or when config.py is
    # bundled next to the executable in --onedir mode by PyInstaller.
    import config # Assuming config.py is in the same directory or accessible by Python path
    HOTKEYS = config.HOTKEYS_CONFIG
    # Optionally load other config items:
    # TRAY_APP_NAME = getattr(config, 'TRAY_APP_NAME_CONFIG', "HotkeyApp") # Default if not in config
    # TRAY_TOOLTIP = getattr(config, 'TRAY_ICON_TOOLTIP_CONFIG', "Hotkey Launcher")
except ImportError:
    print("ERROR: config.py not found or cannot be imported. Using empty hotkey configuration.")
    HOTKEYS = {}
    # TRAY_APP_NAME = "HotkeyApp (No Config)"
    # TRAY_TOOLTIP = "Hotkey Launcher (Config Error)"
except AttributeError:
    print("ERROR: HOTKEYS_CONFIG not found in config.py. Using empty hotkey configuration.")
    HOTKEYS = {}
    # TRAY_APP_NAME = "HotkeyApp (Config Error)"
    # TRAY_TOOLTIP = "Hotkey Launcher (Config Error)"


ICON_FILENAME = "icon.png"  # Keep the filename separate
ICON_PATH = resource_path(ICON_FILENAME) #SHOW IN SYS TRAY. Uses resource_path now.

global_pynput_listener = None

def open_application(app_path):
    try:
        # Refined creationflags logic for more general use
        flags = 0
        console_extensions = ('.bat', '.cmd', '.ps1') # Add other console app extensions if needed
        # Check if it's a known console command or has a console extension
        if any(cmd in app_path.lower() for cmd in ["cmd.exe", "pwsh.exe"]) or \
           app_path.lower().endswith(console_extensions):
            flags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen([app_path], creationflags=flags)
        # print(f"Launched: {app_path}") # Debug
    except FileNotFoundError:
        print(f"Error: Application not found at '{app_path}'. Please check the path.")
    except PermissionError:
        print(f"Error: Permission denied for '{app_path}'. Try running this Python script as Administrator.")
    except Exception as e:
        print(f"An error occurred while trying to open '{app_path}': {e}")

def create_hotkey_actions(): # Uses the HOTKEYS loaded from config
    actions = {}
    if not HOTKEYS: # Check if HOTKEYS dictionary is empty
        print("Warning: No hotkeys are configured.")
        return actions # Return empty actions if no hotkeys

    for hotkey_str, app_path in HOTKEYS.items():
        actions[hotkey_str] = lambda path=app_path: open_application(path)
    return actions

def run_pynput_listener():
    """Sets up and runs the pynput GlobalHotKeys listener."""
    global global_pynput_listener
    # print("Hotkey listener thread started.") # Debug
    hotkey_actions = create_hotkey_actions()

    if not hotkey_actions: # If no actions were created (e.g., empty HOTKEYS)
        print("No hotkey actions to listen for. Pynput listener will not start effectively.")
        return # Don't start the listener if there's nothing to listen for

    try:
        with keyboard.GlobalHotKeys(hotkey_actions) as listener:
            global_pynput_listener = listener
            listener.join()
    except Exception as e:
        print(f"Error in pynput listener thread: {e}")
    finally:
        # print("Hotkey listener thread finished.") # Debug
        pass

def on_exit_clicked(icon, item):
    """Callback when 'Exit' is clicked."""
    # print("Exit clicked. Stopping services...") # Debug
    if global_pynput_listener:
        try:
            global_pynput_listener.stop()
        except Exception as e:
            print(f"Error stopping pynput listener: {e}")
    icon.stop()

if __name__ == "__main__":
    # print("Main script starting...") # Debug

    # Handle case where config might be missing or HOTKEYS is empty early
    if not HOTKEYS:
        print("Critical: Hotkey configuration is empty or failed to load. The application might not be useful.")
        # You could decide to exit here, or show a tray notification,
        # or just let it run without active hotkeys.
        # For now, it will proceed but the listener might not do much.

    listener_thread = threading.Thread(target=run_pynput_listener, daemon=True)
    listener_thread.start()

    # Tray icon setup
    tray_app_display_name = "HotkeyApp" # You could make this configurable too via config.py
    tray_tooltip_text = "Hotkey Launcher"

    try:
        image = Image.open(ICON_PATH)
    except FileNotFoundError:
        print(f"Error: Icon file '{ICON_PATH}' not found. Check if '{ICON_FILENAME}' is in the correct location (same dir as script/exe or as specified by resource_path).")
        image = None
    except Exception as e: # Catch other PIL errors
        print(f"Error loading image '{ICON_PATH}': {e}")
        image = None

    menu_items = (TrayMenuItem('Exit', on_exit_clicked),)

    if image:
        tray_icon = TrayIcon(tray_app_display_name, image, tray_tooltip_text, menu_items)
    else:
        tray_icon = TrayIcon(tray_app_display_name, title=f"{tray_tooltip_text} (No Icon)", menu=menu_items)

    # print("Running tray icon...") # Debug
    try:
        tray_icon.run()
    except Exception as e:
        print(f"Error running tray icon: {e}")
    finally:
        # print("Tray icon stopped. Main script exiting.") # Debug
        if global_pynput_listener and hasattr(global_pynput_listener, 'is_alive') and global_pynput_listener.is_alive():
             try:
                 global_pynput_listener.stop()
             except Exception: # Suppress errors during final stop
                 pass
        if listener_thread.is_alive():
            listener_thread.join(timeout=1)