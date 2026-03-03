---
name: static-data
description: "static_data.xlsx CRUD. 어떤 프로젝트에서도 게임 데이터(시스템, 스킬, 아이템 등) 조회/수정/추가/삭제 시 반드시 이 스킬 사용."
---

# Universal Static Data XLSX Tool

`data/static_data.xlsx` 조작 시 반드시 `python3 .claude/skills/static_data/xlsx_tool.py` 사용.

## Commands

```bash
# 시트 목록 및 구조 파악
python3 .claude/skills/static_data/xlsx_tool.py sheets

# 특정 시트의 컬럼 구성 확인
python3 .claude/skills/static_data/xlsx_tool.py headers <sheet>

# 데이터 조회 (토큰 절약 옵션 필수 활용)
python3 .claude/skills/static_data/xlsx_tool.py read <sheet> --id <key_value>
python3 .claude/skills/static_data/xlsx_tool.py read <sheet> --cols name,value --where type=Buff --limit 10

# 데이터 수정 및 추가
python3 .claude/skills/static_data/xlsx_tool.py set <sheet> <key_value> col=val [col=val ...]
python3 .claude/skills/static_data/xlsx_tool.py add <sheet> col=val [col=val ...]

# 데이터 삭제
python3 .claude/skills/static_data/xlsx_tool.py del <sheet> <key_value>