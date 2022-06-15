# TurboWarp Packager Extras

Extra utilities to use after running the TurboWarp Packager. Currently, it can:

 - Fix the icon of the executable file
 - Create installers

Most people will want to download the prebuilt versions from https://github.com/TurboWarp/packager-extras/releases

This is only intended to be run on Windows systems. It may work with things like Wine, but Wine support is not tested and not a priority.

Written in Python (3.10.1) and PySide 2 (Qt5).

To build locally:

```powershell
# Create virtual env
python -m venv venv

# Activate virtual env with the appropriate script for your platform in venv/Scripts, eg.
.\venv\Scripts\Activate.ps1 # Powershell

# Install dependencies
pip install -r requirements.txt

# Start the app for development
python app.py

# Create final executable for production
pyinstaller --noconsole --onefile --noconfirm --add-data 'third-party;third-party' --splash splash.png -n "turbowarp-packager-extras" app.py
```

The final executable will be stored in the `dist` folder.

If possible, download [UPX](https://github.com/upx/upx/releases) and use the `--upx-dir path/to/upx` to tell pyinstaller where it's installed. Pyinstaller will use this to better compress the app.

Some third-party executables are included inside the repository in the `third-party` folder. See the relevant "README.txt" documents in each folder for more information.
