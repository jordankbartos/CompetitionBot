import os
import zipfile


def zip_dir(dir_path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, dir_path)
                zipf.write(abs_path, rel_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python zip_util.py <dir_path> <zip_path>")
        sys.exit(1)
    zip_dir(sys.argv[1], sys.argv[2])
