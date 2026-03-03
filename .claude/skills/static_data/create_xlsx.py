#!/usr/bin/env python3
"""Create static_data.xlsx from CSV files in Data/ directory using only Python stdlib."""

import csv
import os
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Data"))
OUTPUT = os.path.join(DATA_DIR, "static_data.xlsx")

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_WB_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
NS_SS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
NS_ST_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"


def discover_csvs(data_dir):
    """Auto-discover CSV files from Data/ and Data/Real/ directories."""
    sheets = []
    for f in sorted(os.listdir(data_dir)):
        if f.endswith(".csv"):
            name = f[:-4]
            sheets.append((name, os.path.join(data_dir, f)))

    real_dir = os.path.join(data_dir, "Real")
    if os.path.isdir(real_dir):
        for f in sorted(os.listdir(real_dir)):
            if f.endswith(".csv"):
                name = f[:-4]
                sheets.append((name, os.path.join(real_dir, f)))

    return sheets


def col_letter(index):
    result = ""
    while True:
        result = chr(65 + index % 26) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def is_number(value):
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def xml_declaration(root):
    raw = tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + raw).encode("utf-8")


def build_content_types(sheet_count):
    root = Element("Types", xmlns=NS_CT)
    SubElement(root, "Default", Extension="rels",
               ContentType="application/vnd.openxmlformats-package.relationships+xml")
    SubElement(root, "Default", Extension="xml", ContentType="application/xml")
    SubElement(root, "Override", PartName="/xl/workbook.xml",
               ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    SubElement(root, "Override", PartName="/xl/sharedStrings.xml",
               ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")
    SubElement(root, "Override", PartName="/xl/styles.xml",
               ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")
    for i in range(1, sheet_count + 1):
        SubElement(root, "Override", PartName=f"/xl/worksheets/sheet{i}.xml",
                   ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    return xml_declaration(root)


def build_rels():
    root = Element("Relationships", xmlns=NS_REL)
    SubElement(root, "Relationship", Id="rId1",
               Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
               Target="xl/workbook.xml")
    return xml_declaration(root)


def build_workbook(sheet_names):
    root = Element("workbook", xmlns=NS)
    root.set("xmlns:r", NS_R)
    sheets = SubElement(root, "sheets")
    for i, name in enumerate(sheet_names, 1):
        SubElement(sheets, "sheet", name=name, sheetId=str(i)).\
            set("r:id", f"rId{i}")
    return xml_declaration(root)


def build_workbook_rels(sheet_count):
    root = Element("Relationships", xmlns=NS_REL)
    for i in range(1, sheet_count + 1):
        SubElement(root, "Relationship", Id=f"rId{i}",
                   Type=NS_WB_REL, Target=f"worksheets/sheet{i}.xml")
    SubElement(root, "Relationship", Id=f"rId{sheet_count + 1}",
               Type=NS_SS_REL, Target="sharedStrings.xml")
    SubElement(root, "Relationship", Id=f"rId{sheet_count + 2}",
               Type=NS_ST_REL, Target="styles.xml")
    return xml_declaration(root)


def build_shared_strings(strings_list):
    root = Element("sst", xmlns=NS, count=str(len(strings_list)),
                   uniqueCount=str(len(strings_list)))
    for s in strings_list:
        si = SubElement(root, "si")
        t = SubElement(si, "t")
        if s and (s[0] in (" ", "\t") or s[-1] in (" ", "\t")):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = s if s else ""
    return xml_declaration(root)


def build_styles():
    root = Element("styleSheet", xmlns=NS)
    fonts = SubElement(root, "fonts", count="1")
    font = SubElement(fonts, "font")
    SubElement(font, "sz", val="11")
    fills = SubElement(root, "fills", count="1")
    fill = SubElement(fills, "fill")
    SubElement(fill, "patternFill", patternType="none")
    borders = SubElement(root, "borders", count="1")
    border = SubElement(borders, "border")
    for tag in ("left", "right", "top", "bottom", "diagonal"):
        SubElement(border, tag)
    cellXfs = SubElement(root, "cellXfs", count="1")
    SubElement(cellXfs, "xf", numFmtId="0", fontId="0", fillId="0", borderId="0")
    return xml_declaration(root)


def build_sheet(rows, string_index_map):
    root = Element("worksheet", xmlns=NS)
    sheet_data = SubElement(root, "sheetData")
    for row_idx, row in enumerate(rows, 1):
        row_el = SubElement(sheet_data, "row", r=str(row_idx))
        for col_idx, value in enumerate(row):
            cell_ref = f"{col_letter(col_idx)}{row_idx}"
            if is_number(value):
                c = SubElement(row_el, "c", r=cell_ref)
                v = SubElement(c, "v")
                v.text = value
            else:
                c = SubElement(row_el, "c", r=cell_ref, t="s")
                v = SubElement(c, "v")
                v.text = str(string_index_map[value])
    return xml_declaration(root)


def main():
    csv_entries = discover_csvs(DATA_DIR)
    print(f"Discovered {len(csv_entries)} CSV files\n")

    all_sheets = {}
    all_strings = set()
    sheet_order = []

    for name, csv_path in csv_entries:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = [row for row in reader if any(cell.strip() for cell in row)]

        if not rows:
            print(f"  SKIP (empty): {name}")
            continue

        all_sheets[name] = rows
        sheet_order.append(name)
        for row in rows:
            for cell in row:
                if not is_number(cell):
                    all_strings.add(cell)

        print(f"  Read: {name} ({len(rows) - 1} data rows, {len(rows[0])} cols)")

    strings_list = sorted(all_strings)
    string_index_map = {s: i for i, s in enumerate(strings_list)}

    print(f"\n  Shared strings: {len(strings_list)}")
    print(f"  Sheets: {len(all_sheets)}")

    sheet_count = len(sheet_order)

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", build_content_types(sheet_count))
        zf.writestr("_rels/.rels", build_rels())
        zf.writestr("xl/workbook.xml", build_workbook(sheet_order))
        zf.writestr("xl/_rels/workbook.xml.rels", build_workbook_rels(sheet_count))
        zf.writestr("xl/sharedStrings.xml", build_shared_strings(strings_list))
        zf.writestr("xl/styles.xml", build_styles())

        for i, name in enumerate(sheet_order, 1):
            sheet_xml = build_sheet(all_sheets[name], string_index_map)
            zf.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml)

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\n  Created: {OUTPUT}")
    print(f"  Size: {size_kb:.1f} KB")
    print(f"  Sheets: {', '.join(sheet_order)}")


if __name__ == "__main__":
    main()
