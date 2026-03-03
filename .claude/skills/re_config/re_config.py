#!/usr/bin/env python3
"""리버스 엔지니어링 - MonoBehaviour JSON Config Value Extractor."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from re_common import (
    get_project_from_args, set_default_project, resolve_mono_dir,
    list_mono_projects, SKIP_MONO_FIELDS, format_json_value, get_type_hint
)


def find_files(mono_dir, pattern):
    pattern_lower = pattern.lower()
    return sorted([f for f in os.listdir(mono_dir)
                   if f.endswith(".json") and pattern_lower in f.lower()])


def read_json(mono_dir, filename):
    filepath = os.path.join(mono_dir, filename)
    if not os.path.exists(filepath):
        candidates = find_files(mono_dir, filename.replace(".json", ""))
        if candidates:
            filepath = os.path.join(mono_dir, candidates[0])
        else:
            print(f"File not found: {filename}")
            return None, None
    with open(filepath, "r", encoding="utf-8") as f:
        return os.path.basename(filepath), json.load(f)


def print_config(data, filename, field_filter=None):
    print(f"\n[{filename}]")
    print("-" * 70)
    if not isinstance(data, dict):
        print(f"  (not a dict: {type(data).__name__})")
        return

    entries = []
    for key, value in data.items():
        if key in SKIP_MONO_FIELDS:
            continue
        if field_filter and field_filter.lower() not in key.lower():
            continue
        entries.append((key, format_json_value(value), get_type_hint(value)))

    if not entries:
        print("  (no matching fields)")
        return

    max_key = max(len(e[0]) for e in entries)
    for key, formatted, hint in entries:
        print(f"  {key:<{max_key}} = {formatted:<40} ({hint})")


def cmd_projects():
    projects = list_mono_projects()
    if not projects:
        print("No projects with MonoBehaviour JSON found.")
        return
    print(f"Projects with MonoBehaviour JSON ({len(projects)}):")
    for name, count in projects:
        print(f"  {name:<45} {count:>6,} JSON files")


def cmd_search(mono_dir, project_name, pattern):
    files = find_files(mono_dir, pattern)
    if not files:
        print(f"No files matching '{pattern}' in {project_name}")
        return
    print(f"Found {len(files)} files matching '{pattern}' (project: {project_name}):")
    for f in files[:50]:
        size = os.path.getsize(os.path.join(mono_dir, f))
        print(f"  {f} ({size:,} bytes)")
    if len(files) > 50:
        print(f"  ... and {len(files) - 50} more")


def cmd_read(mono_dir, project_name, filename):
    actual_name, data = read_json(mono_dir, filename)
    if data:
        print(f"(project: {project_name})")
        print_config(data, actual_name)


def cmd_field(mono_dir, filename, field_name):
    actual_name, data = read_json(mono_dir, filename)
    if not data:
        return
    if field_name in data:
        val = data[field_name]
        print(f"{field_name} = {format_json_value(val)} ({get_type_hint(val)})")
        if isinstance(val, (dict, list)):
            print(f"\nRaw JSON:")
            print(json.dumps(val, indent=2, ensure_ascii=False))
    else:
        print(f"Field '{field_name}' not found. Available fields:")
        for key in sorted(data.keys()):
            if key not in SKIP_MONO_FIELDS:
                print(f"  {key}")


def cmd_compare(mono_dir, project_name, filenames):
    names = [n.strip() for n in filenames.split(",")]
    print(f"(project: {project_name})")
    for name in names:
        actual_name, data = read_json(mono_dir, name)
        if data:
            print_config(data, actual_name)


def cmd_grep(mono_dir, project_name, pattern=None, value_min=None, value_max=None):
    pattern_lower = pattern.lower() if pattern else None
    results = []
    for filename in sorted(os.listdir(mono_dir)):
        if not filename.endswith(".json"):
            continue
        try:
            with open(os.path.join(mono_dir, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if key in SKIP_MONO_FIELDS:
                continue
            match = False
            if pattern_lower and pattern_lower in key.lower():
                match = True
            if value_min is not None and isinstance(value, (int, float)):
                if value_min <= value <= value_max:
                    match = True
            if match:
                results.append((filename, key, value))

    if not results:
        print(f"No results (project: {project_name})")
        return
    print(f"Found {len(results)} matches (project: {project_name}):")
    max_f = max(len(r[0]) for r in results[:100])
    max_k = max(len(r[1]) for r in results[:100])
    for fn, key, val in results[:100]:
        print(f"  {fn:<{max_f}}  {key:<{max_k}} = {format_json_value(val)}")
    if len(results) > 100:
        print(f"  ... and {len(results) - 100} more")


def main():
    if len(sys.argv) < 2:
        print("Usage: re_config.py <command> [args] [--project <name>]")
        print("Commands: projects, search, read, field, compare, grep, set-default")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "projects":
        cmd_projects()
        return

    if cmd == "set-default":
        set_default_project(sys.argv[2], "mono")
        return

    project, args = get_project_from_args(sys.argv[2:], "mono")
    if not project:
        print("No project specified. Use --project <name> or set-default.")
        print("Available projects:")
        cmd_projects()
        sys.exit(1)

    mono_dir = resolve_mono_dir(project)
    if not mono_dir:
        print(f"MonoBehaviour directory not found for project '{project}'")
        sys.exit(1)

    project_name = os.path.basename(os.path.dirname(os.path.dirname(mono_dir)))

    if cmd == "search":
        cmd_search(mono_dir, project_name, args[0] if args else "")
    elif cmd == "read":
        cmd_read(mono_dir, project_name, args[0])
    elif cmd == "field":
        cmd_field(mono_dir, args[0], args[1])
    elif cmd == "compare":
        cmd_compare(mono_dir, project_name, args[0])
    elif cmd == "grep":
        if "--value-range" in args:
            idx = args.index("--value-range")
            cmd_grep(mono_dir, project_name, None, float(args[idx+1]), float(args[idx+2]))
        else:
            cmd_grep(mono_dir, project_name, args[0] if args else "")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
