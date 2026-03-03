"""리버스 엔지니어링 스킬 공용 유틸리티.

프로젝트 자동 탐지, 경로 해석, 기본 프로젝트 관리.
"""

import os
import sys
import json
import struct
from pathlib import Path

DECOMPILE_ROOT = "/mnt/f/Decompile"
GHIDRA_ROOT = os.path.join(DECOMPILE_ROOT, "ghidra_extracted_functions")
IL2CPP_ROOT = os.path.join(DECOMPILE_ROOT, "Il2CppDumper_projects")

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROJECT_FILE = os.path.join(SKILLS_DIR, ".re_default_project.json")

SKIP_MONO_FIELDS = {
    "m_GameObject", "m_Enabled", "m_Script", "m_Name",
    "m_EditorHideFlags", "m_EditorClassIdentifier", "m_ObjectHideFlags"
}


def get_default_project(tool_type):
    """기본 프로젝트명 읽기. tool_type: 'ghidra', 'il2cpp', 'mono'"""
    if os.path.exists(DEFAULT_PROJECT_FILE):
        with open(DEFAULT_PROJECT_FILE, "r") as f:
            data = json.load(f)
            return data.get(tool_type) or data.get("default")
    return None


def set_default_project(project_name, tool_type=None):
    """기본 프로젝트 설정."""
    data = {}
    if os.path.exists(DEFAULT_PROJECT_FILE):
        with open(DEFAULT_PROJECT_FILE, "r") as f:
            data = json.load(f)
    if tool_type:
        data[tool_type] = project_name
    else:
        data["default"] = project_name
    with open(DEFAULT_PROJECT_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Default project set: {project_name}" + (f" (for {tool_type})" if tool_type else ""))


def list_ghidra_projects():
    """Ghidra 프로젝트 목록."""
    if not os.path.isdir(GHIDRA_ROOT):
        return []
    return sorted([d for d in os.listdir(GHIDRA_ROOT)
                    if os.path.isdir(os.path.join(GHIDRA_ROOT, d))])


def list_il2cpp_projects():
    """Il2CppDumper 프로젝트 목록."""
    if not os.path.isdir(IL2CPP_ROOT):
        return []
    return sorted([d for d in os.listdir(IL2CPP_ROOT)
                    if os.path.isdir(os.path.join(IL2CPP_ROOT, d))])


def list_mono_projects():
    """MonoBehaviour JSON이 있는 프로젝트 목록."""
    results = []
    for proj in list_il2cpp_projects():
        mono_dir = os.path.join(IL2CPP_ROOT, proj, "Resources", "MonoBehaviour")
        if os.path.isdir(mono_dir):
            count = len([f for f in os.listdir(mono_dir) if f.endswith(".json")])
            results.append((proj, count))
    return results


def resolve_ghidra_dir(project_name):
    """Ghidra 프로젝트 디렉토리 해석 (퍼지 매칭)."""
    return _fuzzy_resolve(GHIDRA_ROOT, project_name)


def resolve_il2cpp_dir(project_name):
    """Il2CppDumper 프로젝트 디렉토리 해석 (퍼지 매칭)."""
    return _fuzzy_resolve(IL2CPP_ROOT, project_name)


def resolve_mono_dir(project_name):
    """MonoBehaviour JSON 디렉토리 해석 (퍼지 매칭)."""
    il2cpp_dir = resolve_il2cpp_dir(project_name)
    if not il2cpp_dir:
        return None
    mono_dir = os.path.join(il2cpp_dir, "Resources", "MonoBehaviour")
    return mono_dir if os.path.isdir(mono_dir) else None


def resolve_code_dir(project_name):
    """C# 소스 디렉토리 해석 (우선순위: vs/ > processed/ > dump.cs)."""
    il2cpp_dir = resolve_il2cpp_dir(project_name)
    if not il2cpp_dir:
        return None, None

    vs_dir = None
    for root, dirs, files in os.walk(il2cpp_dir):
        if "Assembly-CSharp" in dirs:
            asm_dir = os.path.join(root, "Assembly-CSharp")
            for sub_root, sub_dirs, sub_files in os.walk(asm_dir):
                cs_files = [f for f in sub_files if f.endswith(".cs")]
                if cs_files:
                    vs_dir = asm_dir
                    break
            if vs_dir:
                break

    processed_dir = os.path.join(il2cpp_dir, "processed")
    dump_cs = os.path.join(il2cpp_dir, "dump.cs")

    if vs_dir and os.path.isdir(vs_dir):
        return vs_dir, "vs"
    if os.path.isdir(processed_dir):
        return processed_dir, "processed"
    if os.path.exists(dump_cs):
        return dump_cs, "dump"
    return il2cpp_dir, "raw"


def _fuzzy_resolve(base_dir, name):
    """디렉토리 퍼지 매칭 (대소문자 무시, 부분 일치)."""
    if not os.path.isdir(base_dir):
        return None

    exact = os.path.join(base_dir, name)
    if os.path.isdir(exact):
        return exact

    name_lower = name.lower()
    candidates = []
    for d in os.listdir(base_dir):
        full = os.path.join(base_dir, d)
        if not os.path.isdir(full):
            continue
        if d.lower() == name_lower:
            return full
        if name_lower in d.lower():
            candidates.append(full)

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        print(f"Ambiguous project name '{name}'. Candidates:")
        for c in candidates:
            print(f"  {os.path.basename(c)}")
        return candidates[0]
    return None


def get_project_from_args(args, tool_type):
    """CLI args에서 --project 추출 또는 기본값 사용."""
    project = None
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--project" and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    if not project:
        project = get_default_project(tool_type)

    return project, filtered_args


def ieee754_to_float(hex_str):
    """IEEE 754 hex → float."""
    hex_str = hex_str.strip().lower()
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]
    try:
        val = int(hex_str, 16)
        return struct.unpack(">f", struct.pack(">I", val))[0]
    except (ValueError, struct.error):
        return None


def float_to_ieee754(f):
    """float → IEEE 754 hex."""
    return "0x{:08x}".format(struct.unpack(">I", struct.pack(">f", f))[0])


def format_json_value(value):
    """JSON 값을 읽기 좋게 포맷."""
    if isinstance(value, dict):
        if "x" in value and "y" in value:
            z = value.get("z")
            w = value.get("w")
            if w is not None:
                return f"({value['x']}, {value['y']}, {z}, {w})"
            if z is not None:
                return f"({value['x']}, {value['y']}, {z})"
            return f"({value['x']}, {value['y']})"
        if "r" in value and "g" in value:
            return f"Color({value['r']}, {value['g']}, {value['b']}, {value.get('a', 1)})"
        if "m_PathID" in value:
            pid = value["m_PathID"]
            return f"Ref(PathID={pid})" if pid != 0 else "null"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "[]"
        if len(value) <= 5 and all(isinstance(v, (int, float, str)) for v in value):
            return str(value)
        return f"[{len(value)} items]"
    return str(value)


def get_type_hint(value):
    """값의 타입 힌트."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        if "x" in value and "y" in value:
            keys = set(value.keys()) - {"x", "y"}
            if "w" in keys:
                return "Vector4"
            if "z" in keys:
                return "Vector3"
            return "Vector2"
        if "r" in value and "g" in value:
            return "Color"
        if "m_PathID" in value:
            return "ObjectRef"
        return "object"
    if isinstance(value, list):
        return f"array[{len(value)}]"
    return type(value).__name__
