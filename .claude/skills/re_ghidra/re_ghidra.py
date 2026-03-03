#!/usr/bin/env python3
"""리버스 엔지니어링 - Ghidra Decompiled Function Analyzer."""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from re_common import (
    get_project_from_args, set_default_project, resolve_ghidra_dir,
    list_ghidra_projects, ieee754_to_float, float_to_ieee754
)


def find_files(ghidra_dir, pattern):
    pattern_lower = pattern.lower()
    try:
        return sorted([f for f in os.listdir(ghidra_dir)
                       if f.endswith(".c") and pattern_lower in f.lower()])
    except FileNotFoundError:
        return []


def read_function(ghidra_dir, filename):
    filepath = os.path.join(ghidra_dir, filename)
    if not os.path.exists(filepath):
        candidates = find_files(ghidra_dir, filename.replace(".c", ""))
        if candidates:
            filepath = os.path.join(ghidra_dir, candidates[0])
            filename = candidates[0]
        else:
            print(f"File not found: {filename}")
            return None, None
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return filename, f.read()


def extract_constants(content):
    constants = []
    hex_pat = re.compile(r'(0x[0-9a-fA-F]{8})')
    for m in hex_pat.finditer(content):
        hex_val = m.group(1)
        fv = ieee754_to_float(hex_val)
        if fv is not None and 1e-6 < abs(fv) < 1e6:
            ctx_s = max(0, m.start() - 40)
            ctx_e = min(len(content), m.end() + 40)
            ctx = content[ctx_s:ctx_e].replace("\n", " ").strip()
            constants.append((hex_val, fv, ctx))

    float_pat = re.compile(r'(?<![0-9a-fA-Fx])(\d+\.\d+f?)(?![0-9a-fA-Fx])')
    for m in float_pat.finditer(content):
        try:
            val = float(m.group(1).rstrip("f"))
            if abs(val) < 1e6:
                ctx_s = max(0, m.start() - 30)
                ctx_e = min(len(content), m.end() + 30)
                ctx = content[ctx_s:ctx_e].replace("\n", " ").strip()
                constants.append(("literal", val, ctx))
        except ValueError:
            pass
    return constants


def cmd_projects():
    projects = list_ghidra_projects()
    if not projects:
        print("No Ghidra projects found.")
        return
    print(f"Ghidra projects ({len(projects)}):")
    for name in projects:
        d = os.path.join(resolve_ghidra_dir(name) or "", "")
        try:
            count = len([f for f in os.listdir(d) if f.endswith(".c")])
        except (FileNotFoundError, TypeError):
            count = 0
        print(f"  {name:<45} {count:>8,} .c files")


def cmd_search(ghidra_dir, project_name, pattern):
    files = find_files(ghidra_dir, pattern)
    if not files:
        print(f"No files matching '{pattern}' in {project_name}")
        return
    print(f"Found {len(files)} files matching '{pattern}' (project: {project_name}):")
    for f in files[:60]:
        size = os.path.getsize(os.path.join(ghidra_dir, f))
        print(f"  {f} ({size:,} bytes)")
    if len(files) > 60:
        print(f"  ... and {len(files) - 60} more")


def cmd_read(ghidra_dir, filename):
    actual, content = read_function(ghidra_dir, filename)
    if not content:
        return
    print(f"\n[{actual}]")
    print("=" * 70)
    lines = content.split("\n")
    for i, line in enumerate(lines[:200]):
        print(f"  {i+1:4d}| {line}")
    if len(lines) > 200:
        print(f"  ... truncated ({len(lines)} total)")


def cmd_decode(hex_str):
    val = ieee754_to_float(hex_str)
    if val is not None:
        print(f"{hex_str} -> {val}")
        print(f"  Reverse: {val} -> {float_to_ieee754(val)}")
    else:
        print(f"Failed to decode: {hex_str}")


def cmd_methods(ghidra_dir, project_name, classname):
    pattern = classname + "$$"
    results = find_files(ghidra_dir, pattern)
    if not results:
        pattern = classname + "$"
        results = find_files(ghidra_dir, pattern)
    if not results:
        print(f"No methods found for '{classname}' in {project_name}")
        return
    print(f"\nMethods of '{classname}' ({len(results)}) (project: {project_name}):")
    for f in results:
        method = f.replace(".c", "")
        if "$$" in method:
            method = method.split("$$")[-1]
        elif "$" in method:
            method = method.split("$")[-1]
        size = os.path.getsize(os.path.join(ghidra_dir, f))
        print(f"  {method:<50} ({size:>6,} bytes)  [{f}]")


def cmd_grep(ghidra_dir, project_name, pattern):
    pattern_lower = pattern.lower()
    results = []
    for f in sorted(os.listdir(ghidra_dir)):
        if not f.endswith(".c"):
            continue
        try:
            with open(os.path.join(ghidra_dir, f), "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
                if pattern_lower in content.lower():
                    for i, line in enumerate(content.split("\n"), 1):
                        if pattern_lower in line.lower():
                            results.append((f, i, line.strip()))
                            if len(results) >= 80:
                                break
        except IOError:
            continue
        if len(results) >= 80:
            break

    if not results:
        print(f"No results for '{pattern}' (project: {project_name})")
        return
    print(f"Found {len(results)} matches (project: {project_name}):")
    for fn, ln, line in results:
        print(f"  {fn}:{ln}  {line[:120]}")
    if len(results) >= 80:
        print("  ... (limit reached)")


def cmd_constants(ghidra_dir, filename):
    actual, content = read_function(ghidra_dir, filename)
    if not content:
        return
    constants = extract_constants(content)
    if not constants:
        print(f"No constants found in {actual}")
        return
    print(f"\nConstants in [{actual}]:")
    print("-" * 70)
    seen = set()
    for hex_val, fv, ctx in constants:
        key = f"{hex_val}:{fv}"
        if key in seen:
            continue
        seen.add(key)
        if hex_val == "literal":
            print(f"  {fv:<15} (literal)  ...{ctx}...")
        else:
            print(f"  {hex_val} -> {fv:<12.6f}  ...{ctx}...")


def main():
    if len(sys.argv) < 2:
        print("Usage: re_ghidra.py <command> [args] [--project <name>]")
        print("Commands: projects, search, read, decode, methods, grep, constants, set-default")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "projects":
        cmd_projects()
        return
    if cmd == "decode":
        cmd_decode(sys.argv[2])
        return
    if cmd == "set-default":
        set_default_project(sys.argv[2], "ghidra")
        return

    project, args = get_project_from_args(sys.argv[2:], "ghidra")
    if not project:
        print("No project specified. Use --project <name> or set-default.")
        cmd_projects()
        sys.exit(1)

    ghidra_dir = resolve_ghidra_dir(project)
    if not ghidra_dir:
        print(f"Ghidra project not found: '{project}'")
        sys.exit(1)

    project_name = os.path.basename(ghidra_dir)

    if cmd == "search":
        cmd_search(ghidra_dir, project_name, args[0] if args else "")
    elif cmd == "read":
        cmd_read(ghidra_dir, args[0])
    elif cmd == "methods":
        cmd_methods(ghidra_dir, project_name, args[0])
    elif cmd == "grep":
        cmd_grep(ghidra_dir, project_name, args[0])
    elif cmd == "constants":
        cmd_constants(ghidra_dir, args[0])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
