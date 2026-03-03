#!/usr/bin/env python3
"""리버스 엔지니어링 - IL2CPP Dump Code Analyzer."""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from re_common import (
    get_project_from_args, set_default_project, resolve_code_dir,
    resolve_il2cpp_dir, list_il2cpp_projects
)


def find_cs_files(code_dir, code_type, pattern):
    pattern_lower = pattern.lower()
    results = []
    if code_type == "dump":
        return [(code_dir, code_dir)]

    for root, dirs, files in os.walk(code_dir):
        for f in files:
            if not f.endswith(".cs"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, code_dir)
            if pattern_lower in rel.lower() or pattern_lower in f.lower():
                results.append((rel, full))
    return sorted(results)


def parse_class(content):
    fields, methods, properties = [], [], []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("using ") or line.startswith("namespace "):
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        if "(" in line and ")" in line:
            if any(kw in line for kw in ["public ", "private ", "protected ", "internal ", "static ", "virtual ", "override ", "abstract "]):
                if "{ get" not in line and "{ set" not in line:
                    methods.append(line.rstrip(";").rstrip(" {}"))
        if "{ get" in line or "{ set" in line:
            properties.append(line.rstrip())
        if ";" in line and "(" not in line and ")" not in line and "{" not in line and "}" not in line:
            if any(kw in line for kw in ["public ", "private ", "protected ", "internal "]):
                fields.append(line.rstrip(";").strip())
    return fields, methods, properties


def cmd_projects():
    projects = list_il2cpp_projects()
    if not projects:
        print("No Il2CppDumper projects found.")
        return
    print(f"Il2CppDumper projects ({len(projects)}):")
    for name in projects:
        code_dir, code_type = resolve_code_dir(name)
        has_dump = os.path.exists(os.path.join(resolve_il2cpp_dir(name) or "", "dump.cs"))
        has_processed = os.path.isdir(os.path.join(resolve_il2cpp_dir(name) or "", "processed"))
        flags = []
        if code_type == "vs":
            flags.append("vs/")
        if has_processed:
            flags.append("processed/")
        if has_dump:
            flags.append("dump.cs")
        print(f"  {name:<45} [{', '.join(flags)}]")


def cmd_search(code_dir, code_type, project_name, pattern):
    results = find_cs_files(code_dir, code_type, pattern)
    if not results:
        print(f"No files matching '{pattern}' in {project_name}")
        return
    print(f"Found {len(results)} files matching '{pattern}' (project: {project_name}, type: {code_type}):")
    for rel, full in results[:50]:
        size = os.path.getsize(full)
        print(f"  {rel} ({size:,} bytes)")
    if len(results) > 50:
        print(f"  ... and {len(results) - 50} more")


def cmd_read(code_dir, code_type, pattern):
    results = find_cs_files(code_dir, code_type, pattern)
    if not results:
        print(f"No files matching '{pattern}'")
        return

    filepath = results[0][1]
    with open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read()

    fields, methods, properties = parse_class(content)
    print(f"\n[{os.path.basename(filepath)}] ({results[0][0]})")
    print("=" * 60)
    if fields:
        print(f"\nFields ({len(fields)}):")
        for f in fields:
            print(f"  {f}")
    if properties:
        print(f"\nProperties ({len(properties)}):")
        for p in properties:
            print(f"  {p}")
    if methods:
        print(f"\nMethods ({len(methods)}):")
        for m in methods:
            print(f"  {m}")


def cmd_grep(code_dir, code_type, project_name, pattern):
    pattern_lower = pattern.lower()
    results = []
    if code_type == "dump":
        try:
            with open(code_dir, "r", encoding="utf-8-sig") as fh:
                for i, line in enumerate(fh, 1):
                    if pattern_lower in line.lower():
                        results.append(("dump.cs", i, line.strip()))
                        if len(results) >= 80:
                            break
        except (UnicodeDecodeError, IOError):
            pass
    else:
        for root, dirs, files in os.walk(code_dir):
            for f in files:
                if not f.endswith(".cs"):
                    continue
                filepath = os.path.join(root, f)
                rel = os.path.relpath(filepath, code_dir)
                try:
                    with open(filepath, "r", encoding="utf-8-sig") as fh:
                        for i, line in enumerate(fh, 1):
                            if pattern_lower in line.lower():
                                results.append((rel, i, line.strip()))
                                if len(results) >= 80:
                                    break
                except (UnicodeDecodeError, IOError):
                    continue
                if len(results) >= 80:
                    break

    if not results:
        print(f"No results for '{pattern}' (project: {project_name})")
        return
    print(f"Found {len(results)} matches for '{pattern}' (project: {project_name}):")
    for rel, lineno, line in results:
        print(f"  {rel}:{lineno}  {line[:120]}")
    if len(results) >= 80:
        print("  ... (limit reached)")


def cmd_offsets(il2cpp_dir, classname):
    dump_path = os.path.join(il2cpp_dir, "dump.cs")
    if not os.path.exists(dump_path):
        print(f"dump.cs not found in project")
        return

    in_class = False
    class_lines = []
    brace_depth = 0

    with open(dump_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            if not in_class:
                if re.search(rf'\bclass\s+{re.escape(classname)}\b', line, re.IGNORECASE):
                    in_class = True
                    class_lines.append(line.rstrip())
                    brace_depth = line.count("{") - line.count("}")
            else:
                class_lines.append(line.rstrip())
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0:
                    break

    if not class_lines:
        print(f"Class '{classname}' not found in dump.cs")
        return

    print(f"\n[{classname}] from dump.cs")
    print("=" * 60)
    for line in class_lines[:200]:
        stripped = line.strip()
        if "// 0x" in stripped or "Offset:" in stripped or "RVA:" in stripped:
            print(f"  {stripped}")
        elif any(kw in stripped for kw in ["public ", "private ", "protected ", "const ", "static ", "readonly "]):
            if not stripped.startswith("//"):
                print(f"  {stripped}")
    if len(class_lines) > 200:
        print(f"  ... truncated ({len(class_lines)} total)")


def cmd_diff(code_dir, code_type, original_pattern, project_file):
    results = find_cs_files(code_dir, code_type, original_pattern)
    if not results:
        print(f"Original not found: {original_pattern}")
        return

    with open(results[0][1], "r", encoding="utf-8-sig") as f:
        orig_content = f.read()

    if not os.path.exists(project_file):
        print(f"Project file not found: {project_file}")
        return
    with open(project_file, "r", encoding="utf-8-sig") as f:
        proj_content = f.read()

    _, orig_methods, _ = parse_class(orig_content)
    _, proj_methods, _ = parse_class(proj_content)

    def names(items):
        s = set()
        for item in items:
            for t in item.split():
                if "(" in t:
                    s.add(t.split("(")[0])
                    break
        return s

    orig_names = names(orig_methods)
    proj_names = names(proj_methods)
    missing = orig_names - proj_names
    extra = proj_names - orig_names

    print(f"\n[Comparison] Original ({len(orig_names)} methods) vs Project ({len(proj_names)} methods)")
    print(f"Common: {len(orig_names & proj_names)}, Missing: {len(missing)}, Extra: {len(extra)}")
    if missing:
        print(f"\nMissing from project:")
        for m in sorted(missing):
            print(f"  - {m}")
    if extra:
        print(f"\nExtra in project:")
        for m in sorted(extra):
            print(f"  + {m}")


def main():
    if len(sys.argv) < 2:
        print("Usage: re_code.py <command> [args] [--project <name>]")
        print("Commands: projects, search, read, grep, offsets, diff, set-default")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "projects":
        cmd_projects()
        return
    if cmd == "set-default":
        set_default_project(sys.argv[2], "il2cpp")
        return

    project, args = get_project_from_args(sys.argv[2:], "il2cpp")
    if not project:
        print("No project specified. Use --project <name> or set-default.")
        cmd_projects()
        sys.exit(1)

    il2cpp_dir = resolve_il2cpp_dir(project)
    if not il2cpp_dir:
        print(f"Il2CppDumper project not found: '{project}'")
        sys.exit(1)

    code_dir, code_type = resolve_code_dir(project)
    project_name = os.path.basename(il2cpp_dir)

    if cmd == "search":
        cmd_search(code_dir, code_type, project_name, args[0] if args else "")
    elif cmd == "read":
        cmd_read(code_dir, code_type, args[0])
    elif cmd == "grep":
        cmd_grep(code_dir, code_type, project_name, args[0])
    elif cmd == "offsets":
        cmd_offsets(il2cpp_dir, args[0])
    elif cmd == "diff":
        cmd_diff(code_dir, code_type, args[0], args[1])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
