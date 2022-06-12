# TurboWarp Packager Extras

Extra utilities to use after running the TurboWarp Packager. Currently, it can:

 - fix the icon of the executable file
 - create installers

This is only intended to be run on Windows systems. It may work with things like Wine, but it's not tested and not a priority.

Written in Python (only tested on 3.8.0) and PyQt5.

Download prebuilt versions from https://github.com/TurboWarp/packager-extras/releases.

To build locally:

```bash
# Setup virtual env
python -m venv venv
# Activate with the appropriate script for your platform in venv/Scripts, eg.
.\venv\Scripts\Activate.ps1 # Powershell
# Install dependencies
pip install -r requirements.txt
# Start the app
python app.py
# Create executable
pyinstaller --noconsole --onefile --noconfirm --add-data 'third-party;third-party' app.py
```

Some third-party executables are included inside the repository in the `third-party` folder. See the relavent "readme" documents in each folder for more information.
