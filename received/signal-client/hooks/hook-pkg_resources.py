from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules("jaraco")
    + collect_submodules("jaraco.text")
    + collect_submodules("jaraco.functools")
    + collect_submodules("jaraco.context")
    + collect_submodules("setuptools._vendor.jaraco")
)
