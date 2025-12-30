"""Batch runner to minimize multiple section CSVs.

Usage examples:
  python minimize_all.py ./data '2025-01-06T00:00:00Z' '2025-01-08T09:00:00Z'
  python minimize_all.py ./data '2025-01-06T00:00:00Z' '2025-01-08T09:00:00Z' -o ./out -p "BILD*.csv" --dry-run

This script will skip files whose name ends with "_minimized.csv" to avoid reprocessing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

from minimize_csv import minimize_csv


def find_input_files(input_dir: Path, pattern: str) -> List[Path]:
    return sorted(p for p in input_dir.glob(pattern) if p.is_file())


def run_batch(input_dir: Path, instruction_begin: str, second_pass_start: str, waitlist_close: str, output_dir: Path, pattern: str, overwrite: bool, dry_run: bool, overall_dir: Path | None = None) -> Tuple[List[Path], List[Tuple[Path, Exception]]]:
    processed: List[Path] = []
    errors: List[Tuple[Path, Exception]] = []

    # find section files
    section_files = find_input_files(input_dir, pattern)
    # ignore already-minimized files coming from input directories
    section_files = [p for p in section_files if not p.name.endswith("_minimized.csv")]

    # compute bases (everything before the last underscore) for section files
    section_bases = set(p.stem.rsplit("_", 1)[0] for p in section_files)

    # start with section files to process (is_overall_only=False)
    files_to_process: List[Tuple[Path, bool]] = [(p, False) for p in section_files]

    # include overall-only files when overall_dir is specified
    if overall_dir:
        if not overall_dir.exists() or not overall_dir.is_dir():
            print(f"Warning: overall_dir {overall_dir} not found or not a directory; skipping overall files")
        else:
            overall_files = find_input_files(overall_dir, pattern)
            for f in overall_files:
                if f.name.endswith("_minimized.csv"):
                    continue
                base = f.stem.rsplit("_", 1)[0]
                if base not in section_bases:
                    print(f"Including overall-only file: {f.name}")
                    files_to_process.append((f, True))

    for f, is_overall_only in files_to_process:
        suffix = "_nosec_minimized.csv" if is_overall_only else "_minimized.csv"
        out_path = (output_dir / (f.stem + suffix))

        if out_path.exists() and not overwrite:
            print(f"Skipping (output exists): {out_path}")
            continue

        print(f"Processing {f.name} -> {out_path.name}")

        if dry_run:
            continue

        try:
            result = minimize_csv(str(f), instruction_begin, str(out_path), second_pass_start, waitlist_close)
            # minimize_csv returns (final_out_path_str, ending_capacity)
            if result:
                final_out_str, ending_capacity = result
                processed.append(Path(final_out_str))
        except Exception as e:
            errors.append((f, e))
            print(f"Error processing {f.name}: {e}")

    return processed, errors


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch minimize CSV files in a folder")
    parser.add_argument("input_dir", help="Folder containing CSV files to process (sections)")
    parser.add_argument("instruction_begin", help="Instruction begin ISO-8601 UTC datetime string")
    parser.add_argument("second_pass_start", help="Second-pass start ISO-8601 UTC datetime string (required)")
    parser.add_argument("waitlist_close", help="Waitlist close ISO-8601 UTC datetime string (required)")
    parser.add_argument("--overall-dir", help="Optional folder containing overall-class CSVs to use when sections missing", default=None)
    parser.add_argument("-o", "--output-dir", help="Directory to write outputs (defaults to input_dir)", default=None)
    parser.add_argument("-p", "--pattern", help="Glob pattern to match files", default="*.csv")
    parser.add_argument("--overwrite", help="Overwrite existing outputs", action="store_true")
    parser.add_argument("--dry-run", help="Only print planned actions without running", action="store_true")

    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}")
        return 2

    output_dir = Path(args.output_dir) if args.output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    overall_dir = Path(args.overall_dir) if args.overall_dir else None

    processed, errors = run_batch(input_dir, args.instruction_begin, args.second_pass_start, args.waitlist_close, output_dir, args.pattern, args.overwrite, args.dry_run, overall_dir)
    print("\nSummary:")
    print(f"  Processed: {len(processed)} file(s)")
    if errors:
        print(f"  Errors: {len(errors)} file(s)")
        for f, e in errors:
            print(f"    - {f.name}: {e}")

    return 1 if errors else 0

# Sample input: py minimize_all.py 2025Winter-main\2025Winter-main\section '2025-01-06T00:00:00Z' '2024-11-19T00:00:00Z' '2025-01-16T00:00:00Z' --overall-dir 2025Winter-main\2025Winter-main\overall -o 2025_WI --overwrite


if __name__ == "__main__":
    raise SystemExit(main())
