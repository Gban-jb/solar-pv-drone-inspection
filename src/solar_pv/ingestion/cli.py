"""Command line entry point for the Week 1-3 importer."""

from __future__ import annotations

import argparse
from pathlib import Path

from solar_pv.ingestion.importer import init_inspection, scan_inspection, write_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solar-pv-import")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("init", help="Create an inspection folder")
    create.add_argument("folder", type=Path)
    scan = commands.add_parser("scan", help="Scan an inspection folder")
    scan.add_argument("folder", type=Path)
    scan.add_argument("--output", type=Path, help="Output folder for manifest files")
    args = parser.parse_args(argv)

    if args.command == "init":
        print(f"Created inspection folders: {init_inspection(args.folder)}")
        return 0

    try:
        manifest = scan_inspection(args.folder)
        output = args.output or args.folder.resolve().parent / f"{args.folder.name}_output"
        json_path, csv_path = write_manifest(manifest, output)
    except OSError as exc:
        parser.exit(2, f"Import failed: {exc}\n")

    summary = manifest["summary"]
    print(f"Images opened: {summary['images_opened']}/{summary['images_found']}")
    print(f"SCADA CSVs opened: {summary['scada_files_opened']}/{summary['scada_files_found']}")
    for record in (*manifest["images"], *manifest["scada"]):
        detail = record["error"] or ", ".join(record["missing_fields"]) or "complete"
        print(f"{record['status'].upper():7} {record['path']}: {detail}")
    for issue in manifest["folder_issues"]:
        print(f"FOLDER  {issue}")
    print(f"Manifest: {json_path}")
    print(f"Inventory: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
