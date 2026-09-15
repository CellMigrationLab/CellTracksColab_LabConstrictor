from .data_loader import *

# All local notebooks import ``celltracks`` before constructing their shared
# path-selector buttons. Installing this compatibility layer here fixes the
# macOS chooser across the full notebook suite without changing the public
# create_path_selector API. It is a no-op on Windows, Linux, and Google Colab.
try:
    from .macos_native_dialog import install_macos_native_dialog_patch

    install_macos_native_dialog_patch()
except Exception:
    # Path fields remain editable by hand even if the native chooser cannot be
    # installed in an unusual Python/Tk environment. Do not make celltracks
    # itself unimportable because of an optional desktop convenience feature.
    pass
