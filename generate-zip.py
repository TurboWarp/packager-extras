# PowerShell's Compress-Archive creates zips that unix tools have a lot of trouble
# understanding, so we use this small script instead. This makes it easier for people
# to extract and run the program using Wine.

import shutil
name = shutil.make_archive('dist/turbowarp-packager-extras', 'zip', 'dist', 'turbowarp-packager-extras')
print(f'Generated {name}')
