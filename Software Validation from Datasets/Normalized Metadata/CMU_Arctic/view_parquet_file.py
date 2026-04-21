from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


def prompt_folder() -> Path:
    raw = input("Enter folder path containing parquet files: ").strip().strip('"')
    path = Path(raw)
    if not path.exists():
        raise FileNotFoundError(f"Folder does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {path}")
    return path


def find_parquet_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.parquet"))


def process_parquet_file(path: Path, preview_rows: int = 200, print_rows: int = 10) -> tuple[bool, str]:
    try:
        df = pd.read_parquet(path)

        print("\n" + "=" * 80)
        print(f"FILE: {path.name}")
        print("=" * 80)
        print(f"Path: {path}")
        print(f"Rows: {len(df)}")
        print(f"Columns: {len(df.columns)}")

        print("\n=== COLUMN NAMES ===")
        for col in df.columns:
            print(f"- {col}")

        print(f"\n=== FIRST {print_rows} ROWS ===")
        if df.empty:
            print("(DataFrame is empty)")
        else:
            with pd.option_context("display.max_columns", None, "display.width", 200):
                print(df.head(print_rows).to_string(index=False))

        out_path = path.with_name(path.stem + "_preview.csv")
        df.head(preview_rows).to_csv(out_path, index=False)

        print(f"\nCSV preview written to: {out_path}")
        return True, str(out_path)

    except Exception as exc:
        print(f"\nError processing {path.name}: {exc}")
        return False, str(exc)


def main() -> None:
    try:
        folder = prompt_folder()
        parquet_files = find_parquet_files(folder)

        if not parquet_files:
            print("No .parquet files found in that folder.")
            sys.exit(0)

        print(f"\nFound {len(parquet_files)} parquet file(s).")
        print("Processing all files and exporting CSV previews automatically...")

        success_count = 0
        fail_count = 0
        failed_files: list[str] = []

        for parquet_path in parquet_files:
            ok, info = process_parquet_file(parquet_path)
            if ok:
                success_count += 1
            else:
                fail_count += 1
                failed_files.append(f"{parquet_path.name}: {info}")

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total parquet files found: {len(parquet_files)}")
        print(f"Successfully processed:   {success_count}")
        print(f"Failed:                   {fail_count}")

        if failed_files:
            print("\n=== FAILED FILES ===")
            for item in failed_files:
                print(f"- {item}")

    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()