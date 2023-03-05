import sys
import os
import json
import subprocess
import zipfile
import tempfile
import traceback
import re
import shutil
import platform
import ctypes
import urllib.request
import PySide2.QtCore as QtCore
import PySide2.QtWidgets as QtWidgets
import PySide2.QtGui as QtGui
import PIL.Image

VERSION = '1.4.0'
ENABLE_UPDATE_CHECKER = True
UPDATE_CHECKER_URL = 'https://raw.githubusercontent.com/TurboWarp/packager-extras/master/version.json'

def get_executable_name(path):
  files = os.listdir(path)
  for f in files:
    if f.endswith('.exe') and f != 'notification_helper.exe':
      return f
  raise Exception('Cannot find executable')

def parse_package_json(path):
  with open(path, encoding='utf-8') as package_json_file:
    return json.load(package_json_file)

def find_and_parse_package_json(path):
  try:
    # Modern Electron
    return parse_package_json(os.path.join(path, 'resources', 'app', 'package.json'))
  except FileNotFoundError:
    # NW.js, old Electron
    return parse_package_json(os.path.join(path, 'package.json'))

def get_version_from_package_json(data):
  if 'version' in data:
    raw_version = data['version']
    # We parse the version number and regenerate the string to make sure that it's valid
    major, minor, patch = parse_version(raw_version)
    return f'{major}.{minor}.{patch}'
  # No version number. This code path must continue to exist for compatibility reasons
  return '1.0.0'

def try_decode(text):
  try:
    return text.decode("utf-8")
  except UnicodeDecodeError as e:
    print(f"Failed to decode output: {e}")
    return text

def run_command(args, check=True):
  # Don't set check in subprocess.run. We will check it later after logging.
  completed = subprocess.run(
    args,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.PIPE,
    creationflags=subprocess.CREATE_NO_WINDOW
  )
  status = completed.returncode
  print(f'Finished command {completed.args} with exit status {status}.')
  stdout = try_decode(completed.stdout)
  print('Stdout:', stdout)
  stderr = try_decode(completed.stderr)
  print('Stderr:', stderr)
  if check and completed.returncode != 0:
    logged_error = stderr if stderr else stdout
    raise Exception(f"Command {completed.args} failed with code {status}.\n\n{logged_error}")
  return completed

def find_icon(path):
  # Modern Electron
  p = os.path.join(path, 'resources', 'app', 'icon.png')
  if os.path.exists(p):
    return p
  # Old Electron
  p = os.path.join(path, 'icon.png')
  if os.path.exists(p):
    return p
  # NW.js
  package_json = find_and_parse_package_json(path)
  if 'window' in package_json:
    original_icon_name = package_json['window']['icon']
  return os.path.join(path, original_icon_name)

def get_icon_as_ico(path: str) -> str:
  source_icon = find_icon(path)
  image = PIL.Image.open(source_icon)
  ico_path = f'{source_icon}.ico'
  image.save(ico_path, format='ICO')
  return ico_path

def fix_icon(path: str):
  executable_file = os.path.join(path, get_executable_name(path))
  icon = get_icon_as_ico(path)
  run_command([
    os.path.join(os.path.dirname(__file__), 'third-party/rcedit/rcedit-x86.exe'),
    executable_file,
    '--set-icon',
    icon
  ])

def make_temporary_file(filename):
  dirname, pathname = os.path.split(filename)
  return tempfile.TemporaryFile(dir=dirname, prefix=f'twtmp{pathname}')

def make_temporary_directory(filename):
  dirname, pathname = os.path.split(filename)
  return tempfile.TemporaryDirectory(dir=dirname, prefix=f'twtmp{pathname}')

def escape_html(string):
  return (
     string
      .replace('&', '&amp;')
      .replace('>', '&gt;')
      .replace('<', '&lt;')
      .replace('\'', '&apos;')
      .replace('"', '&quot;')
  )

def unescape_html(string):
  return (
    string
      .replace('&quot;', '"')
      .replace('&apos;', '\'')
      .replace('&lt;', '<')
      .replace('&gt;', '>')
      .replace('&amp;', '&')
  )

def parse_project_title(path):
  with open(path, encoding='utf-8') as f:
    contents = f.read()
    title = re.search(r'<title>(.*)<\/title>', contents).group(1)
    return unescape_html(title)

def find_and_parse_project_title(path):
  try:
    # Modern Electron
    return parse_project_title(os.path.join(path, 'resources', 'app', 'index.html'))
  except FileNotFoundError:
    # NW.js, old Electron
    return parse_project_title(os.path.join(path, 'index.html'))

def escape_inno_value(string):
  return (
    string
      .replace('{', '{{')
      .replace('"', '')
  )

def verify_safe_for_filesystem(name):
  unsafe = [
    '/',
    '\\',
    ':',
    '*',
    '?',
    '<',
    '>',
    '|'
  ]
  for i in unsafe:
    if i in name:
      formatted_unsafe = ', '.join(unsafe)
      raise Exception(f'"{name}" can not use the characters {formatted_unsafe}')

def create_installer(path):
  executable_file = get_executable_name(path)
  package_json = find_and_parse_package_json(path)

  package_name = package_json['name']
  verify_safe_for_filesystem(package_name)

  title = find_and_parse_project_title(path)
  version = get_version_from_package_json(package_json)
  output_directory = 'Generated Installer'
  output_name = f'{package_name} Setup'
  absolute_icon_path = get_icon_as_ico(path)
  inno_config = f"""; Automatically generated by TurboWarp Packager Extras.

#define TITLE "{escape_inno_value(title)}"
#define PACKAGE_NAME "{escape_inno_value(package_name)}"
#define EXECUTABLE "{escape_inno_value(executable_file)}"
#define VERSION "{escape_inno_value(version)}"

[Setup]
AppName={{#PACKAGE_NAME}}
AppVersion={{#VERSION}}
WizardStyle=classic
DefaultDirName={{autopf}}\{{#PACKAGE_NAME}}
UninstallDisplayIcon={{app}}\{{#EXECUTABLE}}
DefaultGroupName={{#TITLE}}
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
OutputDir={escape_inno_value(output_directory)}
OutputBaseFilename={escape_inno_value(output_name)}
SetupIconFile={escape_inno_value(os.path.relpath(absolute_icon_path, path))}

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "*"; DestDir: "{{app}}"; Excludes: "*.iss"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{{group}}\{{#TITLE}}"; Filename: "{{app}}\{{#EXECUTABLE}}"
Name: "{{userdesktop}}\{{#TITLE}}"; Filename: "{{app}}\{{#EXECUTABLE}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\{{#EXECUTABLE}}"; Description: "Launch application"; Flags: postinstall nowait skipifsilent

[CustomMessages]
DeleteUserData=Remove user data such as settings and saves?

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  case CurUninstallStep of
    usPostUninstall:
      begin
        if MsgBox(CustomMessage('DeleteUserData'), mbInformation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        begin
          // Electron
          DelTree(ExpandConstant('{{userappdata}}\{{#PACKAGE_NAME}}'), True, True, True);
          // NW.js
          DelTree(ExpandConstant('{{localappdata}}\{{#PACKAGE_NAME}}'), True, True, True);
        end;
      end;
  end;
end;
"""
  print("Inno config", inno_config)
  inno_config_path = os.path.join(path, 'config.iss')
  with open(inno_config_path, 'w', encoding='utf-8') as f:
    f.write(inno_config)

  run_command([
    os.path.join(os.path.dirname(__file__), 'third-party/inno/iscc.exe'),
    inno_config_path
  ])

  expected_output_file = os.path.join(path, output_directory, f'{output_name}.exe')
  if not os.path.exists(expected_output_file):
    raise Exception(f'Inno did not output to expected spot: {expected_output_file}')
  return expected_output_file

def display_success(message):
  print(message)
  msg = QtWidgets.QMessageBox()
  msg.setIcon(QtWidgets.QMessageBox.Information)
  msg.setWindowTitle('Success')
  msg.setText(message)
  msg.exec_()

def handle_error():
  traceback.print_exc()
  display_error(get_debug_info())

def display_error(err):
  msg = QtWidgets.QMessageBox()
  msg.setIcon(QtWidgets.QMessageBox.Critical)
  msg.setWindowTitle('Error')
  msg.setText(f"{err}\n\nInclude a full screenshot of this message in any bug reports or support requests.")
  msg.exec_()

def reveal_in_explorer(path):
  path = path.replace('/', '\\')
  print(f'Trying to reveal {path}')
  run_command([
    'explorer.exe',
    '/select,',
    path
  ], check=False)

def get_debug_info():
  type, value, tb = sys.exc_info()
  # Sometimes there can be significant trailing newlines if the error message was generated from a process output
  exception = str(value).strip()
  platform_info = f"{platform.system()} {platform.release()} {platform.machine()}"
  version_info = VERSION
  if tb is not None:
    raw_tracebacks = reversed(traceback.extract_tb(tb))
    def format_raw_traceback(tb):
      return f"  at {tb.name} in {os.path.basename(tb.filename)}:{tb.lineno}"
    formatted_traceback = "\n".join([format_raw_traceback(i) for i in raw_tracebacks])
  else:
    formatted_traceback = ""
  return f"{exception}\n\nDebug info:\n{formatted_traceback}  ({version_info} {platform_info})"

class BaseThread(QtCore.QThread):
  error = QtCore.Signal(str)

  def run(self):
    try:
      self._run()
    except Exception as e:
      traceback.print_exc()
      self.error.emit(get_debug_info())

def get_zip_inner_folders(zip):
  inner_folders = set()
  for i in zip.filelist:
    filename = i.filename
    inner_folder = filename.split('/')[0]
    inner_folders.add(inner_folder)
  return inner_folders

def get_zip_members_in_folder(zip, prefix):
  return [i.filename for i in zip.filelist if i.filename.startswith(f'{prefix}/')]

def parse_zip(zip):
  if len(zip.filelist) == 0:
    raise Exception('Zip is empty.')

  inner_folders = get_zip_inner_folders(zip)
  if len(inner_folders) == 0:
    raise Exception('Zip has no inner folders.')
  if len(inner_folders) != 1:
    if 'index.html' in inner_folders:
      raise Exception('Zip appears to use a plain zip environment, but the zip must be generated using an "Electron Windows application" or "NW.js Windows application" environment. (found index.html)')
    formatted_inner_folders = ', '.join(inner_folders)
    raise Exception(f'Zip has too many inner folders: {formatted_inner_folders}')

  inner_folder = inner_folders.pop()
  print(f'Inner folder: {inner_folder}')

  def does_file_exist(name):
    for i in zip.filelist:
      if i.filename == f'{inner_folder}/{name}':
        return True
    return False

  def does_any_filename_contain(name):
    for i in zip.filelist:
      if name in i.filename:
        return True
    return False

  electron_linux_libraries = [
    'libffmpeg.so',
    'libvk_swiftshader.so',
    'libvulkan.so.1'
  ]
  for i in electron_linux_libraries:
    if does_file_exist(i):
      raise Exception(f'Zip appears to be an Electron Linux app, but this tool only supports Windows apps. (found {i})')

  nwjs_linux_libraries = [
    'lib/libnw.so',
    'lib/libnode.so',
    'lib/libGLESv2.so',
    'lib/libffmpeg.so',
    'lib/libEGL.so'
  ]
  for i in nwjs_linux_libraries:
    if does_file_exist(i):
      raise Exception(f'Zip appears to be an NW.js Linux app, but this tool only supports Windows apps. (found {i})')

  if does_any_filename_contain('.app/'):
    raise Exception('Zip appears to be a macOS app, but this tool only supports Windows apps. (found a .app file)')

  if not does_file_exist('resources.pak'):
    raise Exception('Zip is not a valid Electron or NW.js application. (resources.pak is missing)')

  return inner_folder, get_zip_members_in_folder(zip, inner_folder)

class ExtractWorker(BaseThread):
  extracted = QtCore.Signal(str)

  def __init__(self, parent, filename, dest):
    super().__init__(parent)
    self.filename = filename
    self.dest = dest

  def _run(self):
    with zipfile.ZipFile(self.filename) as zip:
      inner_folder, members_to_extract = parse_zip(zip)
      zip.extractall(self.dest, members_to_extract)
      extracted_contents = os.path.join(self.dest, inner_folder)
    print(f'Extracted to: {extracted_contents}')
    self.extracted.emit(extracted_contents)


class OptionsWorker(BaseThread):
  progress_update = QtCore.Signal(str)
  success = QtCore.Signal()

  def __init__(self, parent):
    super().__init__(parent)
    self.temporary_directory = parent.temporary_directory.name
    self.extracted_contents = parent.extracted_contents
    self.filename = parent.filename
    self.should_fix_icon = parent.fix_icon_checkbox.isChecked()
    self.should_create_installer = parent.create_installer_checkbox.isChecked()
    self.installer_destination = parent.installer_destination

  def update_progress(self, text):
    print(text)
    self.progress_update.emit(text)

  def rezip(self):
    self.update_progress('Recompressing (slow!)')
    with make_temporary_file(self.filename) as temporary_archive:
      generated_archive_name = shutil.make_archive(temporary_archive.name, 'zip', self.temporary_directory)
      shutil.move(generated_archive_name, self.filename)

  def _run(self):
    if self.should_fix_icon:
      self.update_progress('Creating EXE with fixed icon')
      fix_icon(self.extracted_contents)
      self.rezip()
      self.update_progress('Replaced EXE in original zip with fixed icon EXE')

    if self.should_create_installer:
      self.update_progress('Creating installer (very slow!!)')
      generated_installer_path = create_installer(self.extracted_contents)
      shutil.move(generated_installer_path, self.installer_destination)
      self.update_progress('Created installer')

    self.success.emit()

def parse_version(full_version):
  # Returns (major, minor, patch) or raises an Exception
  version_number = full_version.split('-')[0]
  parts = [int(i) for i in version_number.split('.')]
  if len(parts) != 3:
    raise Exception(f'Version number does not have exactly 3 parts: {full_version}')
  return parts

def is_out_of_date(current_version, latest_version):
  major1, minor1, patch1 = parse_version(current_version)
  major2, minor2, patch2 = parse_version(latest_version)
  if major2 > major1: return True
  if major1 > major2: return False
  if minor2 > minor1: return True
  if minor1 > minor2: return False
  if patch2 > patch1: return True
  if patch1 > patch2: return False
  return False

class UpdateCheckerWorker(BaseThread):
  update_available = QtCore.Signal(str)

  def _run(self):
    with urllib.request.urlopen(UPDATE_CHECKER_URL) as response:
      status = response.status
      if status != 200:
        raise Exception(f'Unexpected status code while checking for updates: {status}')

      contents = response.read()
      parsed = json.loads(contents)
      latest_version = parsed['latest']
      if is_out_of_date(VERSION, latest_version):
        self.update_available.emit(latest_version)


class ExtractingWidget(QtWidgets.QWidget):
  def __init__(self):
    super().__init__()

    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    self.setLayout(layout)

    label = QtWidgets.QLabel('Extracting...')
    label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
    label.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(label)


class ProgressWidget(QtWidgets.QWidget):
  def __init__(self):
    super().__init__()

    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    self.setLayout(layout)

    label = QtWidgets.QLabel('This may take a while. Please be patient. Avoid closing the application until this process finishes.')
    label.setWordWrap(True)
    layout.addWidget(label)

    self.text_edit = QtWidgets.QTextEdit()
    self.text_edit.setReadOnly(True)
    self.text_edit.setFixedHeight(80)
    layout.addWidget(self.text_edit)

  def handle_progress_update(self, text):
    self.text_edit.append(text)


class ProjectOptionsWidget(QtWidgets.QWidget):
  process_started = QtCore.Signal()
  process_ended = QtCore.Signal()
  remove_me = QtCore.Signal()

  def __init__(self, filename):
    super().__init__()

    self.filename = filename
    self.temporary_directory = make_temporary_directory(self.filename)

    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    self.setLayout(layout)

    self.extracting_widget = ExtractingWidget()
    layout.addWidget(self.extracting_widget)
    self.progress_widget = None

    self.installer_destination = None

    extract_worker = ExtractWorker(self, self.filename, self.temporary_directory.name)
    extract_worker.error.connect(self.extract_worker_error)
    extract_worker.extracted.connect(self.finished_extract)
    extract_worker.start()

  def finished_extract(self, extracted_contents):
    self.process_ended.emit()

    self.extracting_widget.setParent(None)
    layout = self.layout()
    self.extracted_contents = extracted_contents

    label = QtWidgets.QLabel()
    label.setText(f'Opened: <b>{escape_html(os.path.basename(self.filename))}</b>')
    label.setFixedHeight(label.sizeHint().height())
    layout.addWidget(label)

    self.fix_icon_checkbox = QtWidgets.QCheckBox('Fix icon of .EXE')
    self.fix_icon_checkbox.setChecked(True)
    layout.addWidget(self.fix_icon_checkbox)

    self.create_installer_checkbox = QtWidgets.QCheckBox('Create installer')
    self.create_installer_checkbox.setChecked(True)
    layout.addWidget(self.create_installer_checkbox)

    self.ok_button = QtWidgets.QPushButton('Continue')
    self.ok_button.clicked.connect(self.click)
    self.ok_button.setFixedHeight(self.ok_button.sizeHint().height() * 2)
    layout.addWidget(self.ok_button)

    self.cancel_button = QtWidgets.QPushButton('Go Back')
    self.cancel_button.clicked.connect(self.click_cancel)
    self.cancel_button.setFixedHeight(self.cancel_button.sizeHint().height())
    layout.addWidget(self.cancel_button)

  def pick_installer_destination(self):
    suggested_path = os.path.join(os.path.dirname(self.filename), f'{os.path.splitext(os.path.basename(self.filename))[0]} Setup.exe')
    installer_destination = QtWidgets.QFileDialog.getSaveFileName(self, 'Select where to save the installer', suggested_path, 'Executable files (*.exe)')[0]
    if not installer_destination:
      return None
    return installer_destination

  def set_enable_controls(self, enabled):
    if hasattr(self, 'fix_icon_checkbox'): self.fix_icon_checkbox.setVisible(enabled)
    if hasattr(self, 'create_installer_checkbox'): self.create_installer_checkbox.setVisible(enabled)
    if hasattr(self, 'ok_button'): self.ok_button.setVisible(enabled)
    if hasattr(self, 'cancel_button'): self.cancel_button.setVisible(enabled)

  def click(self):
    try:
      should_fix_icon = self.fix_icon_checkbox.isChecked()
      should_create_installer = self.create_installer_checkbox.isChecked()
      if not should_fix_icon and not should_create_installer:
        raise Exception('You have to check at least one of the boxes.')

      if should_create_installer:
        self.installer_destination = self.pick_installer_destination()
        if self.installer_destination is None:
          return

      self.process_started.emit()

      worker = OptionsWorker(self)
      worker.error.connect(self.worker_error)
      worker.success.connect(self.worker_finished)

      self.set_enable_controls(False)
      self.progress_widget = ProgressWidget()
      self.layout().addWidget(self.progress_widget)

      worker.progress_update.connect(self.progress_widget.handle_progress_update)
      worker.start()
    except Exception:
      self.cleanup()
      handle_error()

  def click_cancel(self):
    self.remove()

  def cleanup(self):
    self.process_ended.emit()
    if self.progress_widget:
      self.progress_widget.setParent(None)
      self.progress_widget = None
    self.set_enable_controls(True)

  def extract_worker_error(self, err):
    self.worker_error(err)
    self.remove()

  def worker_error(self, err):
    display_error(err)
    self.cleanup()

  def worker_finished(self):
    display_success('Success')
    if self.installer_destination:
      reveal_in_explorer(self.installer_destination)
    self.cleanup()
    self.remove()

  def remove(self):
    self.temporary_directory.cleanup()
    self.remove_me.emit()


class SelectWidget(QtWidgets.QWidget):
  file_selected = QtCore.Signal(str)

  def __init__(self):
    super().__init__()

    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    self.setLayout(layout)

    button = QtWidgets.QPushButton()
    button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Expanding)
    button.clicked.connect(self.click)

    button_label = QtWidgets.QLabel('Select or drop an Electron or NW.js .zip file generated by the packager', button)
    button_label.setAlignment(QtCore.Qt.AlignCenter)
    button_label.setWordWrap(True)

    button_layout = QtWidgets.QVBoxLayout(button)
    button_layout.addWidget(button_label)

    layout.addWidget(button)

  def click(self):
    downloads_folder = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DownloadLocation)
    file_result = QtWidgets.QFileDialog.getOpenFileName(self, 'Select packager output', downloads_folder, 'Zip files (*.zip)')
    file = file_result[0]
    if file:
      self.file_selected.emit(file)


class MainWindow(QtWidgets.QWidget):
  def __init__(self):
    super().__init__()

    self.resize(300, 200)

    dirname = os.path.dirname(__file__)
    self.setWindowIcon(QtGui.QIcon(os.path.join(dirname, 'icon.png')))
    self.setWindowTitle('Packager Extras')

    self.setWindowFlags(QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMinimizeButtonHint)
    self.setAcceptDrops(True)

    layout = QtWidgets.QVBoxLayout()
    self.setLayout(layout)

    self.label = QtWidgets.QLabel('Report bugs <a href="https://github.com/TurboWarp/packager-extras/issues">on GitHub</a>. Only run on files you trust.')
    self.label.setWordWrap(True)
    self.label.setFixedHeight(self.label.sizeHint().height())
    self.label.setOpenExternalLinks(True)
    layout.addWidget(self.label)

    self.select_widget = SelectWidget()
    self.select_widget.file_selected.connect(self.on_file_selected)
    layout.addWidget(self.select_widget)

    if ENABLE_UPDATE_CHECKER:
      self.update_checker_worker = UpdateCheckerWorker()
      self.update_checker_worker.update_available.connect(self.update_available)
      self.update_checker_worker.start()

    self.configure_widget = None
    self.is_process_ongoing = False

  def dragEnterEvent(self, event):
    if event.mimeData().hasUrls():
      event.accept()
    else:
      event.ignore()

  def dropEvent(self, event):
    file = event.mimeData().urls()[0].toLocalFile()
    if not self.is_process_ongoing:
      self.on_file_selected(file)

  def closeEvent(self, event):
    if self.is_process_ongoing:
      reply = QtWidgets.QMessageBox.question(
        self,
        'Confirm',
        'Are you sure you want to leave? The app is still running. We can\'t guarantee it will clean up properly if you close it preemptively.',
        QtWidgets.QMessageBox.Yes,
        QtWidgets.QMessageBox.No
      )
      if reply == QtWidgets.QMessageBox.Yes:
        event.accept()
      else:
        event.ignore()

  def on_file_selected(self, file):
    print(f'Opening {file}')
    try:
      if self.configure_widget:
        raise Exception('Already have a file open')
      self.is_process_ongoing = True
      self.configure_widget = ProjectOptionsWidget(file)
      self.configure_widget.remove_me.connect(self.on_project_done)
      self.configure_widget.process_started.connect(self.on_process_started)
      self.configure_widget.process_ended.connect(self.on_process_ended)
      self.layout().addWidget(self.configure_widget)
    except Exception:
      handle_error()
    else:
      self.select_widget.setParent(None)

  def on_process_started(self):
    self.is_process_ongoing = True

  def on_process_ended(self):
    self.is_process_ongoing = False

  def on_project_done(self):
    self.configure_widget.setParent(None)
    self.configure_widget.deleteLater()
    self.configure_widget = None
    self.layout().addWidget(self.select_widget)

  def update_available(self, latest_version):
    print('An update is available')
    self.label.setText(f'An update is available. <a href="https://github.com/TurboWarp/packager-extras/releases">Download v{escape_html(latest_version)} from GitHub releases</a>. ' + self.label.text())

def close_pyinstaller_splash():
  if '_PYIBoot_SPLASH' in os.environ:
    try:
      import pyi_splash
      pyi_splash.close()
    except ImportError:
      pass

def main():
  # this terrible thing makes the app icon actually appear on the Windows task bar
  ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'org.turbowarp.packager.extras.' + VERSION)

  os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
  app = QtWidgets.QApplication(sys.argv)
  window = MainWindow()
  close_pyinstaller_splash()
  window.show()
  sys.exit(app.exec_())


if __name__ == '__main__':
  main()
