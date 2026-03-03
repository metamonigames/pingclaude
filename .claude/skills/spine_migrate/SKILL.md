---
name: spine-migrate
description: "Spine .skel/.atlas 에셋을 spine-unity 4.2 호환 포맷으로 변환. Resources/TextAsset → Assets/Resources/Spine 마이그레이션."
---

# Spine Asset Migration Tool

Spine `.skel` (바이너리) + `.atlas` + 텍스처 PNG를 spine-unity 4.2 런타임용으로 변환하는 도구.

## 사용법

```bash
# 전체 마이그레이션 (Resources/TextAsset → Assets/Resources/Spine)
python3 .claude/skills/spine_migrate/spine_migrate.py

# 특정 에셋만 변환
python3 .claude/skills/spine_migrate/spine_migrate.py --names Elevator,Corridor,Ground

# 소스/대상 디렉토리 지정
python3 .claude/skills/spine_migrate/spine_migrate.py --src Resources/TextAsset --dst Assets/Resources/Spine --tex Resources/Texture2D

# Import JSON 생성 (Spine Editor Import Data용, atlas에서 개별 스프라이트 추출)
python3 .claude/skills/spine_migrate/spine_migrate.py --extract-sprites --names Elevator

# 건조 실행 (실제 변환 없이 대상 파일 목록만 출력)
python3 .claude/skills/spine_migrate/spine_migrate.py --dry-run
```

## 기능

1. **버전 변환**: `.skel` 3.5~4.1 → 4.2 (SpineSkeletonDataConverter 자동 빌드)
2. **확장자 변경**: `.skel` → `.skel.bytes`, `.atlas` → `.atlas.txt` (Unity TextAsset 인식)
3. **텍스처 복사**: atlas 참조 PNG를 `Resources/Texture2D/`에서 대상 폴더로 복사
4. **스프라이트 추출** (`--extract-sprites`): Atlas PNG에서 개별 스프라이트 추출 + Import JSON 생성
5. **PMA 역변환**: Premultiplied Alpha 텍스처를 Straight Alpha로 변환 (스프라이트 추출 시)

## 의존성

- Python 3.8+, Pillow (스프라이트 추출 시)
- CMake 3.10+, GCC 10+ 또는 Clang 12+ (SpineSkeletonDataConverter 빌드)
- Git (SpineSkeletonDataConverter 클론)

## 출력 구조

```
Assets/Resources/Spine/
├── {Name}.skel.bytes       # 4.2 변환된 바이너리
├── {Name}.atlas.txt        # atlas 텍스트
├── {Name}.png              # atlas 텍스처
└── Projects/{Name}/        # (--extract-sprites 시)
    ├── {Name}.json         # Spine Editor Import Data용
    └── images/             # 개별 스프라이트
```
