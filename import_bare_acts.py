import argparse
from pathlib import Path

from backend import app, import_bare_acts_folder, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Import bare Act PDF sections into the local provision database.")
    parser.add_argument("folder", nargs="?", default="Bare Acts ", help="Folder containing bare Act PDFs.")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_absolute():
        folder = Path(__file__).resolve().parent / folder
    if not folder.exists():
        raise SystemExit(f"Folder not found: {folder}")

    with app.app_context():
        init_db()
        results = import_bare_acts_folder(folder)

    total = sum(results.values())
    print(f"Imported {total} provisions from {folder}")
    for filename, count in results.items():
        print(f"{filename}: {count}")


if __name__ == "__main__":
    main()
