[app]

# (str) Title of your application
title = 本地文件浏览器

# (str) Package name
package.name = filebrowser

# (str) Package domain (needed for android/ios packaging)
package.domain = com.openclaw.filebrowser

# (str) Source code where the main.py lives
source.dir = .

# (str) Application icon (leave empty for default)
# icon = icon.png

# (str) Presplash (.jpg or .png)
# presplash.filename = presplash.png

# (str) Application versioning
version = 2.0.0

# (list) Permissions
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

# (bool) Accept Android SDK licenses
android.accept_sdk_license = True

# (int) Android API level to use
android.api = 34

# (int) Minimum API level
android.minapi = 21

# (int) Android SDK version to use
android.sdk = 34

# (str) Android NDK version to use
android.ndk = 25c

# (bool) Use Android's private storage
android.private_storage = True

# (str) Requirements (comma separated)
requirements = python3,kivy==2.3.1,Pillow,pillow-heif,ffpyplayer

# (str) Android entry point
services = none

# (str) Application log level (debug, info, warning, error)
log_level = 2

# (bool) Preserve environment (for debugging)
preserve.env = False

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,kv,atlas,json

# (list) List of inclusions (patterns)
source.include_patterns = *

# (list) List of exclusions (patterns)
source.exclude_patterns = buildozer.spec, .git, __pycache__, *.pyc

[buildozer]

# (int) Log level (0=error, 1=warning, 2=info, 3=debug)
log_level = 2

# (str) WARN: which target to build
target = android
