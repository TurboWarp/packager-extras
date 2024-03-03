# TurboWarp Packager Extras

Extra utilities to use after running the TurboWarp Packager. Currently, it can:

 - Fix the icon of the executable file
 - Create installers

Most people will want to download the prebuilt versions from https://github.com/TurboWarp/packager-extras/releases

This is only intended to be run on Windows systems. It may work with things like Wine, but Wine support is not tested and not a priority.

Written in Python (3.12.2) and PyQt5.

To build locally:

```powershell
# Create virtual env
python -m venv venv

# Activate virtual env with the appropriate script for your platform in venv/Scripts, eg.
.\venv\Scripts\Activate.ps1 # PowerShell

# Install dependencies
pip install -r requirements.txt

# Start the app for development
python app.py

# Create final executable for production
pyinstaller --noconsole --onefile --noconfirm --add-data 'third-party;third-party' --add-data 'icon.png;.' --splash splash.png --name "turbowarp-packager-extras" --icon icon.ico --upx-dir upx app.py
```

For best results, optionally download [UPX](https://github.com/upx/upx/releases) and store upx.exe in the `upx` directory. Pyinstaller uses UPX to generate a significantly smaller app.

The final executable will be stored in the `dist` folder.

Some third-party executables are included inside the repository in the `third-party` folder. See the relevant "README.txt" documents in each folder for more information.
