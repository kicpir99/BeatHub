import os
import shutil

source_dir = r"d:\Projekt\BeatHub_Upload"
part1_dir = r"d:\Projekt\BeatHub_Upload_Czesc1"
part2_dir = r"d:\Projekt\BeatHub_Upload_Czesc2"
part3_dir = r"d:\Projekt\BeatHub_Upload_Czesc3"

for d in [part1_dir, part2_dir, part3_dir]:
    if os.path.exists(d):
        shutil.rmtree(d)

# Kopiowanie funkcji zachowującej strukturę
def copy_with_structure(src_path, dest_base):
    rel_path = os.path.relpath(src_path, source_dir)
    dest_path = os.path.join(dest_base, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(src_path, dest_path)

# Podział plików
for root, _, files in os.walk(source_dir):
    for file in files:
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, source_dir)
        
        # Cześć 2: Szablony i Static (najwięcej plików)
        if rel_path.startswith(r"music\static") or rel_path.startswith(r"music\templates"):
            copy_with_structure(full_path, part2_dir)
        # Cześć 3: Reszta folderu music
        elif rel_path.startswith(r"music") and not (rel_path.startswith(r"music\static") or rel_path.startswith(r"music\templates")):
            copy_with_structure(full_path, part3_dir)
        # Cześć 1: Cała reszta (core, media, manage.py itp)
        else:
            copy_with_structure(full_path, part1_dir)

print("Podział zakończony pomyślnie!")
