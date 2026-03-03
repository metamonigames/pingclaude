#!/usr/bin/env python3
"""
static_data.py — RUNuts game data xlsx CRUD tool for Claude Code.
Pure Python stdlib. No external dependencies.

Usage:
  python3 Data/static_data.py sheets
  python3 Data/static_data.py headers <sheet>
  python3 Data/static_data.py read <sheet> [--id N] [--cols c1,c2] [--where col=val ...] [--limit N]
  python3 Data/static_data.py set <sheet> <id> col=val [col=val ...]
  python3 Data/static_data.py add <sheet> col=val [col=val ...]
  python3 Data/static_data.py del <sheet> <id>
"""

import csv
import io
import os
import sys
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

# 파일이 스킬 폴더 안에 있으므로, 프로젝트 루트의 Data 폴더를 가리키도록 수정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 스킬 폴더(.claude/skills/static_data)에서 프로젝트 루트의 Data 폴더로 접근
XLSX_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Data/static_data.xlsx"))

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_WB_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
NS_SS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
NS_ST_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_REL_BARE = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_OD_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"


# ─── Helpers ───

def col_letter(index):
    r = ""
    while True:
        r = chr(65 + index % 26) + r
        index = index // 26 - 1
        if index < 0:
            break
    return r


def parse_col_index(cell_ref):
    col = 0
    for c in cell_ref:
        if "A" <= c <= "Z":
            col = col * 26 + (ord(c) - 64)
        else:
            break
    return col - 1


def is_number(v):
    if not v:
        return False
    try:
        float(v)
        return True
    except ValueError:
        return False


def xml_bytes(root):
    raw = tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + raw).encode("utf-8")


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def find_key_col(headers):
    """Find the key/id column. Checks: id, Id, ID, key, quest_id, condition_id, then first column."""
    for candidate in ("id", "Id", "ID", "key", "quest_id", "condition_id"):
        if candidate in headers:
            return candidate
    return headers[0] if headers else None


# ─── Read xlsx ───

def read_xlsx(path=XLSX_PATH):
    """Returns {sheet_name: (headers: list[str], rows: list[list[str]])}"""
    if not os.path.exists(path):
        die(f"File not found: {path}")

    with zipfile.ZipFile(path, "r") as zf:
        ss = _read_shared_strings(zf)
        sheet_map = _build_sheet_map(zf)
        result = {}
        for name, sheet_path in sheet_map.items():
            all_rows = _read_sheet_rows(zf, sheet_path, ss)
            if all_rows:
                result[name] = (all_rows[0], all_rows[1:])
            else:
                result[name] = ([], [])
    return result


def _read_shared_strings(zf):
    try:
        with zf.open("xl/sharedStrings.xml") as f:
            import xml.etree.ElementTree as ET
            root = ET.parse(f).getroot()
    except KeyError:
        return []
    strings = []
    for si in root.findall(f"{NS}si"):
        t = si.find(f"{NS}t")
        if t is not None:
            strings.append(t.text or "")
        else:
            parts = []
            for r in si.findall(f"{NS}r"):
                rt = r.find(f"{NS}t")
                if rt is not None:
                    parts.append(rt.text or "")
            strings.append("".join(parts))
    return strings


def _build_sheet_map(zf):
    import xml.etree.ElementTree as ET
    with zf.open("xl/workbook.xml") as f:
        wb = ET.parse(f).getroot()
    with zf.open("xl/_rels/workbook.xml.rels") as f:
        rels = ET.parse(f).getroot()

    rid_to_target = {}
    for rel in rels.findall(f"{NS_REL}Relationship"):
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            rid_to_target[rid] = "xl/" + target

    result = {}
    sheets_el = wb.find(f"{NS}sheets")
    if sheets_el is not None:
        for sheet in sheets_el.findall(f"{NS}sheet"):
            name = sheet.get("name")
            rid = sheet.get(f"{NS_R}id")
            if name and rid and rid in rid_to_target:
                result[name] = rid_to_target[rid]
    return result


def _read_sheet_rows(zf, sheet_path, shared_strings):
    import xml.etree.ElementTree as ET
    with zf.open(sheet_path) as f:
        root = ET.parse(f).getroot()

    sheet_data = root.find(f"{NS}sheetData")
    if sheet_data is None:
        return []

    all_rows = []
    for row_el in sheet_data.findall(f"{NS}row"):
        cells = []
        max_col = -1
        for cell in row_el.findall(f"{NS}c"):
            ref = cell.get("r")
            if not ref:
                continue
            ci = parse_col_index(ref)
            if ci > max_col:
                max_col = ci
            ct = cell.get("t")
            v_el = cell.find(f"{NS}v")
            if ct == "s" and v_el is not None:
                idx = int(v_el.text)
                val = shared_strings[idx] if idx < len(shared_strings) else ""
            elif v_el is not None:
                val = v_el.text or ""
            else:
                val = ""
            cells.append((ci, val))

        row = [""] * (max_col + 1) if max_col >= 0 else []
        for ci, val in cells:
            row[ci] = val
        all_rows.append(row)

    return all_rows


# ─── Write xlsx ───

def write_xlsx(sheets_data, path=XLSX_PATH):
    """sheets_data: {name: (headers, rows)} in insertion order."""
    all_strings = set()
    ordered_names = list(sheets_data.keys())

    for headers, rows in sheets_data.values():
        for cell in headers:
            if not is_number(cell):
                all_strings.add(cell)
        for row in rows:
            for cell in row:
                if not is_number(cell):
                    all_strings.add(cell)

    strings_list = sorted(all_strings)
    si_map = {s: i for i, s in enumerate(strings_list)}
    sc = len(ordered_names)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", xml_bytes(_mk_content_types(sc)))
        zf.writestr("_rels/.rels", xml_bytes(_mk_rels()))
        zf.writestr("xl/workbook.xml", xml_bytes(_mk_workbook(ordered_names)))
        zf.writestr("xl/_rels/workbook.xml.rels", xml_bytes(_mk_wb_rels(sc)))
        zf.writestr("xl/sharedStrings.xml", xml_bytes(_mk_shared_strings(strings_list)))
        zf.writestr("xl/styles.xml", xml_bytes(_mk_styles()))
        for i, name in enumerate(ordered_names, 1):
            headers, rows = sheets_data[name]
            all_rows = [headers] + rows
            zf.writestr(f"xl/worksheets/sheet{i}.xml", xml_bytes(_mk_sheet(all_rows, si_map)))


def _mk_content_types(sc):
    r = Element("Types", xmlns=NS_CT)
    SubElement(r, "Default", Extension="rels",
               ContentType="application/vnd.openxmlformats-package.relationships+xml")
    SubElement(r, "Default", Extension="xml", ContentType="application/xml")
    SubElement(r, "Override", PartName="/xl/workbook.xml",
               ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    SubElement(r, "Override", PartName="/xl/sharedStrings.xml",
               ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")
    SubElement(r, "Override", PartName="/xl/styles.xml",
               ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")
    for i in range(1, sc + 1):
        SubElement(r, "Override", PartName=f"/xl/worksheets/sheet{i}.xml",
                   ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    return r


def _mk_rels():
    r = Element("Relationships", xmlns=NS_REL_BARE)
    SubElement(r, "Relationship", Id="rId1", Type=NS_OD_REL, Target="xl/workbook.xml")
    return r


def _mk_workbook(names):
    r = Element("workbook", xmlns=NS[1:-1])
    r.set("xmlns:r", NS_R[1:-1])
    sheets = SubElement(r, "sheets")
    for i, n in enumerate(names, 1):
        s = SubElement(sheets, "sheet", name=n, sheetId=str(i))
        s.set("r:id", f"rId{i}")
    return r


def _mk_wb_rels(sc):
    r = Element("Relationships", xmlns=NS_REL_BARE)
    for i in range(1, sc + 1):
        SubElement(r, "Relationship", Id=f"rId{i}", Type=NS_WB_REL_TYPE,
                   Target=f"worksheets/sheet{i}.xml")
    SubElement(r, "Relationship", Id=f"rId{sc+1}", Type=NS_SS_REL_TYPE, Target="sharedStrings.xml")
    SubElement(r, "Relationship", Id=f"rId{sc+2}", Type=NS_ST_REL_TYPE, Target="styles.xml")
    return r


def _mk_shared_strings(strings):
    r = Element("sst", xmlns=NS[1:-1], count=str(len(strings)), uniqueCount=str(len(strings)))
    for s in strings:
        si = SubElement(r, "si")
        t = SubElement(si, "t")
        if s and (s[0] in (" ", "\t") or s[-1] in (" ", "\t")):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = s if s else ""
    return r


def _mk_styles():
    r = Element("styleSheet", xmlns=NS[1:-1])
    fonts = SubElement(r, "fonts", count="1")
    font = SubElement(fonts, "font")
    SubElement(font, "sz", val="11")
    fills = SubElement(r, "fills", count="1")
    fill = SubElement(fills, "fill")
    SubElement(fill, "patternFill", patternType="none")
    borders = SubElement(r, "borders", count="1")
    border = SubElement(borders, "border")
    for tag in ("left", "right", "top", "bottom", "diagonal"):
        SubElement(border, tag)
    xfs = SubElement(r, "cellXfs", count="1")
    SubElement(xfs, "xf", numFmtId="0", fontId="0", fillId="0", borderId="0")
    return r


def _mk_sheet(all_rows, si_map):
    r = Element("worksheet", xmlns=NS[1:-1])
    sd = SubElement(r, "sheetData")
    for ri, row in enumerate(all_rows, 1):
        row_el = SubElement(sd, "row", r=str(ri))
        for ci, val in enumerate(row):
            ref = f"{col_letter(ci)}{ri}"
            if is_number(val):
                c = SubElement(row_el, "c", r=ref)
                SubElement(c, "v").text = val
            else:
                c = SubElement(row_el, "c", r=ref, t="s")
                SubElement(c, "v").text = str(si_map[val])
    return r


# ─── Commands ───

def cmd_sheets():
    data = read_xlsx()
    print(f"{'Sheet':<26} {'Rows':>5}  {'Cols':>4}  {'Key Column'}")
    print("─" * 55)
    total = 0
    for name, (headers, rows) in data.items():
        key_col = find_key_col(headers) or "-"
        print(f"{name:<26} {len(rows):>5}  {len(headers):>4}  {key_col}")
        total += len(rows)
    print("─" * 55)
    print(f"{'TOTAL':<26} {total:>5}  {len(data):>4} sheets")


def cmd_headers(sheet):
    data = read_xlsx()
    if sheet not in data:
        die(f"Sheet '{sheet}' not found. Available: {', '.join(data.keys())}")
    headers = data[sheet][0]
    print(",".join(headers))


def cmd_read(sheet, args):
    data = read_xlsx()
    if sheet not in data:
        die(f"Sheet '{sheet}' not found. Available: {', '.join(data.keys())}")

    headers, rows = data[sheet]
    target_id = None
    cols = None
    wheres = []
    limit = None

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--id" and i + 1 < len(args):
            target_id = args[i + 1]
            i += 2
        elif a == "--cols" and i + 1 < len(args):
            cols = [c.strip() for c in args[i + 1].split(",")]
            i += 2
        elif a == "--where" and i + 1 < len(args):
            wheres.append(args[i + 1])
            i += 2
        elif a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    # Filter by key column (--id)
    if target_id is not None:
        key_col = find_key_col(headers)
        if not key_col:
            die("Sheet has no recognizable key column")
        id_idx = headers.index(key_col)
        matched = [r for r in rows if len(r) > id_idx and r[id_idx] == target_id]
        if not matched:
            die(f"{key_col}={target_id} not found in '{sheet}'")
        row = matched[0]
        sel_headers = cols if cols else headers
        for h in sel_headers:
            if h in headers:
                hi = headers.index(h)
                val = row[hi] if hi < len(row) else ""
                print(f"{h}: {val}")
        return

    # Filter by --where
    filtered = rows
    for w in wheres:
        if "=" not in w:
            continue
        wc, wv = w.split("=", 1)
        wc = wc.strip()
        wv = wv.strip()
        if wc in headers:
            wi = headers.index(wc)
            filtered = [r for r in filtered if len(r) > wi and r[wi] == wv]

    if limit is not None:
        filtered = filtered[:limit]

    if cols:
        col_indices = [headers.index(c) for c in cols if c in headers]
        sel_headers = [c for c in cols if c in headers]
    else:
        col_indices = list(range(len(headers)))
        sel_headers = headers

    print("\t".join(sel_headers))
    for row in filtered:
        vals = []
        for ci in col_indices:
            vals.append(row[ci] if ci < len(row) else "")
        print("\t".join(vals))

    if not cols:
        print(f"\n({len(filtered)} rows)")


def cmd_set(sheet, row_id, assignments):
    data = read_xlsx()
    if sheet not in data:
        die(f"Sheet '{sheet}' not found")

    headers, rows = data[sheet]
    key_col = find_key_col(headers)
    if not key_col:
        die("Sheet has no recognizable key column")

    id_idx = headers.index(key_col)
    target_row = None
    for row in rows:
        if len(row) > id_idx and row[id_idx] == str(row_id):
            target_row = row
            break

    if target_row is None:
        die(f"{key_col}={row_id} not found in '{sheet}'")

    changes = []
    for a in assignments:
        if "=" not in a:
            continue
        col, val = a.split("=", 1)
        col = col.strip()
        val = val.strip()
        if col not in headers:
            die(f"Column '{col}' not found. Available: {','.join(headers)}")
        ci = headers.index(col)
        old_val = target_row[ci] if ci < len(target_row) else ""
        while len(target_row) <= ci:
            target_row.append("")
        target_row[ci] = val
        changes.append(f"  {col}: {old_val} → {val}")

    write_xlsx(data)
    print(f"Updated {sheet} {key_col}={row_id}:")
    for c in changes:
        print(c)


def cmd_add(sheet, assignments):
    data = read_xlsx()
    if sheet not in data:
        die(f"Sheet '{sheet}' not found")

    headers, rows = data[sheet]
    key_col = find_key_col(headers)

    # Auto-increment numeric key
    new_id = None
    if key_col:
        id_idx = headers.index(key_col)
        max_id = 0
        for row in rows:
            if len(row) > id_idx and row[id_idx]:
                try:
                    rid = int(row[id_idx])
                    if rid > max_id:
                        max_id = rid
                except ValueError:
                    pass
        if max_id > 0:
            new_id = str(max_id + 1)

    new_row = [""] * len(headers)
    if key_col and new_id:
        new_row[headers.index(key_col)] = new_id

    for a in assignments:
        if "=" not in a:
            continue
        col, val = a.split("=", 1)
        col = col.strip()
        val = val.strip()
        if key_col and col == key_col and new_id:
            continue
        if col not in headers:
            die(f"Column '{col}' not found. Available: {','.join(headers)}")
        new_row[headers.index(col)] = val

    rows.append(new_row)
    write_xlsx(data)

    display_id = new_id if new_id else new_row[0]
    print(f"Added to {sheet} ({key_col}={display_id}):")
    for i, h in enumerate(headers):
        if new_row[i]:
            print(f"  {h}: {new_row[i]}")


def cmd_del(sheet, row_id):
    data = read_xlsx()
    if sheet not in data:
        die(f"Sheet '{sheet}' not found")

    headers, rows = data[sheet]
    key_col = find_key_col(headers)
    if not key_col:
        die("Sheet has no recognizable key column")

    id_idx = headers.index(key_col)
    original_len = len(rows)
    new_rows = [r for r in rows if not (len(r) > id_idx and r[id_idx] == str(row_id))]

    if len(new_rows) == original_len:
        die(f"{key_col}={row_id} not found in '{sheet}'")

    data[sheet] = (headers, new_rows)
    write_xlsx(data)
    print(f"Deleted {sheet} {key_col}={row_id} ({original_len} → {len(new_rows)} rows)")


# ─── Main ───

def usage():
    print("""Usage:
  static_data.py sheets                              List all sheets
  static_data.py headers <sheet>                     Show column names
  static_data.py read <sheet> [options]               Read data
    --id N         Single row by key column
    --cols c1,c2   Select columns
    --where c=v    Filter rows (repeatable)
    --limit N      Max rows
  static_data.py set <sheet> <id> col=val [...]      Update row
  static_data.py add <sheet> col=val [...]            Add row (auto key)
  static_data.py del <sheet> <id>                    Delete row""")


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "sheets":
        cmd_sheets()
    elif cmd == "headers":
        if len(sys.argv) < 3:
            die("Usage: headers <sheet>")
        cmd_headers(sys.argv[2])
    elif cmd == "read":
        if len(sys.argv) < 3:
            die("Usage: read <sheet> [options]")
        cmd_read(sys.argv[2], sys.argv[3:])
    elif cmd == "set":
        if len(sys.argv) < 5:
            die("Usage: set <sheet> <id> col=val [...]")
        cmd_set(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif cmd == "add":
        if len(sys.argv) < 4:
            die("Usage: add <sheet> col=val [...]")
        cmd_add(sys.argv[2], sys.argv[3:])
    elif cmd == "del":
        if len(sys.argv) < 4:
            die("Usage: del <sheet> <id>")
        cmd_del(sys.argv[2], sys.argv[3])
    else:
        die(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
