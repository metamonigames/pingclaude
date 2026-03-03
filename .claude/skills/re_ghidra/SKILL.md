---
name: re-ghidra
description: "리버스 엔지니어링: Ghidra 디컴파일 C 함수에서 실제 로직/상수/알고리즘 추출. 프로젝트 자동 탐지."
---

# Reverse Engineering - Ghidra Function Analyzer

Ghidra 디컴파일 C 코드에서 실제 런타임 로직, IEEE 754 float 상수, 알고리즘을 추출.

## 소스 경로 (자동 탐지)
```
/mnt/f/Decompile/ghidra_extracted_functions/{project}/
```
파일명 패턴: `Namespace.Class$Method.c` 또는 `Class$$Method.c`

## 사용법

```bash
# 사용 가능한 프로젝트 목록 + .c 파일 수
python3 .claude/skills/re_ghidra/re_ghidra.py projects

# 클래스/메서드 검색 (파일명 부분 일치)
python3 .claude/skills/re_ghidra/re_ghidra.py search "ElevatorView"
python3 .claude/skills/re_ghidra/re_ghidra.py search "BattleManager" --project S2RD

# 특정 메서드 읽기
python3 .claude/skills/re_ghidra/re_ghidra.py read "ElevatorView$$LateUpdate"

# IEEE 754 float 디코딩 (hex → float)
python3 .claude/skills/re_ghidra/re_ghidra.py decode 0x40333333
# → 2.8

# 특정 클래스의 모든 메서드 목록
python3 .claude/skills/re_ghidra/re_ghidra.py methods "MineshaftFactory"

# 코드 내 특정 패턴 검색
python3 .claude/skills/re_ghidra/re_ghidra.py grep "SetEase"

# float 상수 추출 (파일에서 DAT_ 참조 디코딩)
python3 .claude/skills/re_ghidra/re_ghidra.py constants "ElevatorView$$LateUpdate"

# 기본 프로젝트 설정
python3 .claude/skills/re_ghidra/re_ghidra.py set-default "Idle-miner-tycoon"
```

## IEEE 754 Float 빠른 참조

| Hex | Float | 설명 |
|-----|-------|------|
| `0x3f800000` | 1.0 | |
| `0x3f000000` | 0.5 | |
| `0x40000000` | 2.0 | |
| `0x40400000` | 3.0 | |
| `0x40800000` | 4.0 | |
| `0x41200000` | 10.0 | |
| `0x42c80000` | 100.0 | |
| `0xbf800000` | -1.0 | |
