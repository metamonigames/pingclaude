---
name: re-code
description: "리버스 엔지니어링: IL2CPP dump에서 클래스/필드/메서드 시그니처 분석. 프로젝트 자동 탐지."
---

# Reverse Engineering - IL2CPP Code Analyzer

Il2CppDumper의 C# stub (dump.cs, processed/, DummyDll/, vs/)에서 클래스 구조를 분석.

## 소스 경로 (자동 탐지)
```
/mnt/f/Decompile/Il2CppDumper_projects/{project}/
├── dump.cs                  # 전체 메타데이터 (필드 오프셋 포함)
├── processed/               # 개별 .cs 파일 (플랫)
├── DummyDll/                # 어셈블리별 DLL
└── vs/Assembly-CSharp/      # VS 프로젝트 구조 (일부 프로젝트만)
    └── _Scripts/             # 네임스페이스별 폴더 구조
```

## 사용법

```bash
# 사용 가능한 프로젝트 목록 + 각 프로젝트 구조 요약
python3 .claude/skills/re_code/re_code.py projects

# 클래스 검색 (파일명 부분 일치)
python3 .claude/skills/re_code/re_code.py search "MineshaftModel"
python3 .claude/skills/re_code/re_code.py search "StageManager" --project S2RD

# 클래스 전체 읽기 (필드 + 메서드 시그니처)
python3 .claude/skills/re_code/re_code.py read "MineshaftModel"

# 메서드/필드명으로 전체 검색
python3 .claude/skills/re_code/re_code.py grep "StashResource"

# dump.cs에서 필드 오프셋 분석
python3 .claude/skills/re_code/re_code.py offsets "MineshaftConfig"

# 프로젝트 코드와 비교 (원본 vs 복원)
python3 .claude/skills/re_code/re_code.py diff "MineshaftModel" "/path/to/project/MineshaftModel.cs"

# 기본 프로젝트 설정
python3 .claude/skills/re_code/re_code.py set-default "Idle Mider Tycoon"
```

## C# 소스 탐지 우선순위

1. `vs/Assembly-CSharp/_Scripts/` (VS 프로젝트 구조, 폴더 계층 보존)
2. `processed/` (플랫 .cs 파일)
3. `dump.cs` (단일 파일, 전체 메타데이터)
