"""macOS-native file/folder chooser compatibility for CellTracksColab notebooks.

CellTracksColab notebooks historically use ``tkinter.filedialog`` from an
ipywidgets button. On macOS those dialogs can appear behind JupyterLab/browser
windows, especially when they are parented to a withdrawn Tk root. Repeatedly
creating Tk roots around native open panels has also been unreliable on some
macOS/Tk combinations.

This module keeps the existing notebook API unchanged. On macOS it routes
``askdirectory`` and ``askopenfilename`` through the operating system's native
Standard Additions chooser using ``osascript``. Windows and Linux are left
untouched.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

_PATCHED = False

_APPLESCRIPT = r'''
on run argv
    set pickerMode to item 1 of argv
    set promptText to item 2 of argv
    set initialPath to item 3 of argv

    tell current application
        activate
        try
            if pickerMode is "folder" then
                if initialPath is not "" then
                    set pickedItem to choose folder with prompt promptText default location (POSIX file initialPath)
                else
                    set pickedItem to choose folder with prompt promptText
                end if
            else
                if initialPath is not "" then
                    set pickedItem to choose file with prompt promptText default location (POSIX file initialPath)
                else
                    set pickedItem to choose file with prompt promptText
                end if
            end if
            return POSIX path of pickedItem
        on error number -128
            return ""
        end try
    end tell
end run
'''


def _existing_initial_directory(value: Any) -> str:
    """Return an existing directory suitable for a native macOS chooser."""
    raw = str(value or "").strip()
    if not raw:
        return str(Path.home())

    candidate = Path(raw).expanduser()
    try:
        candidate = candidate.resolve(strict=False)
    except OSError:
        candidate = Path(os.path.abspath(os.path.expanduser(raw)))

    if candidate.is_dir():
        return str(candidate)
    if candidate.is_file():
        return str(candidate.parent)

    parent = candidate.parent
    while parent != parent.parent and not parent.is_dir():
        parent = parent.parent
    return str(parent if parent.is_dir() else Path.home())


def _choose_with_macos_dialog(*, mode: str, title: str, initialdir: Any) -> str:
    """Open a macOS-native chooser and return a POSIX path or an empty string."""
    osascript = Path("/usr/bin/osascript")
    if not osascript.is_file():
        raise RuntimeError("/usr/bin/osascript is unavailable")

    completed = subprocess.run(
        [
            str(osascript),
            "-e",
            _APPLESCRIPT,
            mode,
            title,
            _existing_initial_directory(initialdir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    # User cancellation is normal and should behave exactly like Tk's dialogs:
    # return an empty string rather than surfacing an error in the notebook.
    if completed.returncode != 0:
        lowered = stderr.lower()
        if "-128" in stderr or "user canceled" in lowered or "user cancelled" in lowered:
            return ""
        raise RuntimeError(stderr or f"osascript exited with status {completed.returncode}")

    return stdout


def install_macos_native_dialog_patch() -> bool:
    """Patch Tk file dialogs on macOS while preserving the notebook API.

    Returns ``True`` when the patch is newly installed and ``False`` on other
    platforms or when it was already active.
    """
    global _PATCHED

    if sys.platform != "darwin" or _PATCHED:
        return False

    from tkinter import filedialog

    original_askdirectory: Callable[..., str] = filedialog.askdirectory
    original_askopenfilename: Callable[..., str] = filedialog.askopenfilename

    def askdirectory(**options: Any) -> str:
        try:
            return _choose_with_macos_dialog(
                mode="folder",
                title=str(options.get("title") or "Select a folder"),
                initialdir=options.get("initialdir"),
            )
        except Exception:
            # If the native route is unavailable, retain the existing Tk
            # fallback but do not parent it to the notebook's withdrawn root;
            # that hidden parent is a common source of macOS focus failures.
            fallback = dict(options)
            fallback.pop("parent", None)
            return original_askdirectory(**fallback)

    def askopenfilename(**options: Any) -> str:
        try:
            # AppleScript filters by macOS type/UTI rather than Tk wildcards.
            # Keep the native chooser permissive; notebooks already validate
            # the selected path/file downstream.
            return _choose_with_macos_dialog(
                mode="file",
                title=str(options.get("title") or "Select a file"),
                initialdir=options.get("initialdir"),
            )
        except Exception:
            fallback = dict(options)
            fallback.pop("parent", None)
            return original_askopenfilename(**fallback)

    filedialog.askdirectory = askdirectory
    filedialog.askopenfilename = askopenfilename
    _PATCHED = True
    return True
