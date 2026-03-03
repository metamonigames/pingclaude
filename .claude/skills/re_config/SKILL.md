---
name: re-config
description: "리버스 엔지니어링: MonoBehaviour JSON에서 SerializeField 수치 조회. 프로젝트 자동 탐지."
---

# Reverse Engineering - Config Value Extractor

Il2CppDumper로 추출한 MonoBehaviour JSON에서 ScriptableObject/Prefab의 SerializeField 실제 값을 조회.

## 소스 경로 (자동 탐지)
```
/mnt/f/Decompile/Il2CppDumper_projects/{project}/Resources/MonoBehaviour/
```

## 사용법

```bash
# 사용 가능한 프로젝트 목록
python3 .claude/skills/re_config/re_config.py projects

# Config 파일 검색 (기본 프로젝트 또는 --project 지정)
python3 .claude/skills/re_config/re_config.py search "MineshaftConfig"
python3 .claude/skills/re_config/re_config.py search "WeaponConfig" --project pokopoko

# Config 파일의 모든 필드 출력
python3 .claude/skills/re_config/re_config.py read "MineshaftConfig"
python3 .claude/skills/re_config/re_config.py read "StageConfig" --project S2RD

# 특정 필드값만 조회
python3 .claude/skills/re_config/re_config.py field "MineshaftConfig" "_mineshaftOffsetY"

# 여러 Config 한번에 비교
python3 .claude/skills/re_config/re_config.py compare "MineshaftConfig,ElevatorView,GroundConfig"

# 필드명으로 전체 JSON 검색 (어떤 Config에 해당 필드가 있는지)
python3 .claude/skills/re_config/re_config.py grep "_yOffsetToCorridor"

# 수치 범위 필터 (특정 범위의 float 값을 가진 필드 찾기)
python3 .claude/skills/re_config/re_config.py grep --value-range 1.5 2.0

# 기본 프로젝트 설정
python3 .claude/skills/re_config/re_config.py set-default "Idle Mider Tycoon"
```

## 프로젝트 탐지 규칙

1. `--project` 인자가 있으면 해당 프로젝트 사용
2. 없으면 `.re_default_project` 파일에서 기본 프로젝트 읽기
3. 둘 다 없으면 프로젝트 목록 출력 후 선택 요청

## 출력 형식

```
[MineshaftConfig.json] (project: Idle Mider Tycoon)
----------------------------------------------------------------------
  _noMineshaftOffsetY  = 3.45           (float)
  _mineshaftOffsetY    = 1.69           (float)
  _rocksOffsetMax      = (100.0, 10.0)  (Vector2)
```
