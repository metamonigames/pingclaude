#!/usr/bin/env python3
"""Spine asset migration tool: .skel/.atlas → spine-unity 4.2 compatible format."""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

DEFAULT_SRC = "Resources/TextAsset"
DEFAULT_DST = "Assets/Resources/Spine"
DEFAULT_TEX = "Resources/Texture2D"
TARGET_VERSION = "4.2.11"
CONVERTER_REPO = "https://github.com/wang606/SpineSkeletonDataConverter.git"


def find_project_root():
    cwd = os.getcwd()
    while True:
        if os.path.exists(os.path.join(cwd, "Assets")) and os.path.exists(os.path.join(cwd, "Packages")):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            return os.getcwd()
        cwd = parent


def ensure_converter():
    converter_dir = os.path.join(tempfile.gettempdir(), "SpineSkeletonDataConverter")
    binary = os.path.join(converter_dir, "build", "SpineSkeletonDataConverter")

    if os.path.exists(binary):
        return binary

    print("[1/2] Cloning SpineSkeletonDataConverter...")
    if os.path.exists(converter_dir):
        shutil.rmtree(converter_dir)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", CONVERTER_REPO, converter_dir],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: git clone failed: {result.stderr}")
        sys.exit(1)

    print("[2/2] Building SpineSkeletonDataConverter...")
    build_dir = os.path.join(converter_dir, "build")
    os.makedirs(build_dir, exist_ok=True)

    result = subprocess.run(
        ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release"],
        cwd=build_dir, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: cmake configure failed: {result.stderr}")
        sys.exit(1)

    nproc = os.cpu_count() or 4
    result = subprocess.run(
        ["cmake", "--build", ".", "--config", "Release", f"-j{nproc}"],
        cwd=build_dir, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: cmake build failed: {result.stderr}")
        sys.exit(1)

    if not os.path.exists(binary):
        print("  ERROR: Binary not found after build")
        sys.exit(1)

    print(f"  Converter ready: {binary}\n")
    return binary


def get_atlas_textures(atlas_path):
    textures = []
    with open(atlas_path, "r") as f:
        for line in f:
            stripped = line.strip()
            if stripped.endswith(".png"):
                textures.append(stripped)
    return textures


def parse_atlas(atlas_path):
    regions = []
    current_page = None
    current_region = None
    atlas_scale = 1.0

    with open(atlas_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.rstrip("\r\n").strip()

        if not stripped:
            continue

        if stripped.endswith(".png"):
            current_page = {"name": stripped}
            current_region = None
            continue

        if ":" not in stripped and current_page is not None:
            if current_region is not None:
                regions.append(current_region)
            current_region = {
                "name": stripped,
                "page": current_page["name"],
                "rotate": False,
                "bounds": None,
                "offsets": None,
            }
            continue

        if ":" in stripped and current_page is not None:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if current_region is None:
                if key == "scale":
                    atlas_scale = float(value)
                continue

            if key == "bounds":
                current_region["bounds"] = [int(x) for x in value.split(",")]
            elif key == "rotate":
                current_region["rotate"] = value == "90" or value.lower() == "true"
            elif key == "offsets":
                current_region["offsets"] = [int(x) for x in value.split(",")]

    if current_region is not None:
        regions.append(current_region)

    return regions, atlas_scale


def unpremultiply_alpha(img):
    from PIL import Image
    pixels = img.load()
    width, height = img.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if 0 < a < 255:
                r = min(255, int(r * 255 / a))
                g = min(255, int(g * 255 / a))
                b = min(255, int(b * 255 / a))
                pixels[x, y] = (r, g, b, a)
    return img


def extract_sprite(atlas_img, region, atlas_scale):
    from PIL import Image
    x, y, w, h = region["bounds"]
    rotated = region["rotate"]

    if rotated:
        crop_box = (x, y, x + h, y + w)
    else:
        crop_box = (x, y, x + w, y + h)

    sprite = atlas_img.crop(crop_box)

    if rotated:
        sprite = sprite.transpose(Image.Transpose.ROTATE_90)

    orig_w, orig_h = w, h
    off_x, off_y = 0, 0

    if region["offsets"]:
        off_x, off_y, orig_w, orig_h = region["offsets"]

    if orig_w != w or orig_h != h:
        full_sprite = Image.new("RGBA", (orig_w, orig_h), (0, 0, 0, 0))
        full_sprite.paste(sprite, (off_x, off_y))
        sprite = full_sprite

    scale_factor = 1.0 / atlas_scale
    if abs(scale_factor - 1.0) > 0.01:
        new_w = int(orig_w * scale_factor)
        new_h = int(orig_h * scale_factor)
        sprite = sprite.resize((new_w, new_h), Image.Resampling.LANCZOS)

    return sprite


def extract_sprites_for_asset(base_name, atlas_path, tex_dir, output_dir, converter):
    from PIL import Image

    projects_dir = os.path.join(output_dir, "Projects", base_name)
    images_dir = os.path.join(projects_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    skel_bytes = os.path.join(output_dir, f"{base_name}.skel.bytes")
    if not os.path.exists(skel_bytes):
        print(f"    No .skel.bytes found for {base_name}")
        return

    with tempfile.NamedTemporaryFile(suffix=".skel", delete=False) as tmp_in:
        shutil.copy2(skel_bytes, tmp_in.name)
        tmp_in_path = tmp_in.name

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_out:
        tmp_out_path = tmp_out.name

    try:
        result = subprocess.run(
            [converter, tmp_in_path, tmp_out_path, "-v", TARGET_VERSION],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"    skel→json conversion failed: {result.stderr.strip()}")
            return

        with open(tmp_out_path, "r") as f:
            spine_data = json.load(f)
    finally:
        os.unlink(tmp_in_path)
        if os.path.exists(tmp_out_path):
            os.unlink(tmp_out_path)

    skeleton = spine_data.get("skeleton", {})
    skeleton["images"] = "./images/"
    skeleton["audio"] = ""
    spine_data["skeleton"] = skeleton

    json_path = os.path.join(projects_dir, f"{base_name}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spine_data, f, indent=2, ensure_ascii=False)

    regions, atlas_scale = parse_atlas(atlas_path)
    textures = get_atlas_textures(atlas_path)

    for tex_name in textures:
        tex_path = os.path.join(tex_dir, tex_name)
        if not os.path.exists(tex_path):
            tex_path = os.path.join(os.path.dirname(atlas_path), tex_name)
        if not os.path.exists(tex_path):
            print(f"    Texture not found: {tex_name}")
            continue

        atlas_img = Image.open(tex_path).convert("RGBA")
        atlas_img = unpremultiply_alpha(atlas_img)

        seen = set()
        for region in regions:
            if region["page"] != tex_name:
                continue
            name = region["name"]
            if name in seen:
                continue
            seen.add(name)

            if "/" in name:
                folder, filename = name.rsplit("/", 1)
                sprite_dir = os.path.join(images_dir, folder)
            else:
                sprite_dir = images_dir
                filename = name

            os.makedirs(sprite_dir, exist_ok=True)
            sprite = extract_sprite(atlas_img, region, atlas_scale)
            sprite.save(os.path.join(sprite_dir, f"{filename}.png"))

    sprite_count = sum(1 for _ in glob.glob(os.path.join(images_dir, "**", "*.png"), recursive=True))
    print(f"    Extracted {sprite_count} sprites + {base_name}.json")


def main():
    parser = argparse.ArgumentParser(description="Spine asset migration tool")
    parser.add_argument("--src", default=DEFAULT_SRC, help="Source directory with .skel/.atlas files")
    parser.add_argument("--dst", default=DEFAULT_DST, help="Destination directory for converted assets")
    parser.add_argument("--tex", default=DEFAULT_TEX, help="Texture source directory (PNG files)")
    parser.add_argument("--names", help="Comma-separated asset names to process (default: all)")
    parser.add_argument("--extract-sprites", action="store_true", help="Extract individual sprites + import JSON")
    parser.add_argument("--dry-run", action="store_true", help="List targets without converting")
    parser.add_argument("--version", default=TARGET_VERSION, help=f"Target Spine version (default: {TARGET_VERSION})")
    args = parser.parse_args()

    root = find_project_root()
    src_dir = os.path.join(root, args.src)
    dst_dir = os.path.join(root, args.dst)
    tex_dir = os.path.join(root, args.tex)

    if not os.path.exists(src_dir):
        print(f"ERROR: Source directory not found: {src_dir}")
        sys.exit(1)

    skel_files = sorted(glob.glob(os.path.join(src_dir, "*.skel")))
    atlas_files = sorted(glob.glob(os.path.join(src_dir, "*.atlas")))

    all_bases = set()
    for sf in skel_files:
        all_bases.add(os.path.splitext(os.path.basename(sf))[0])
    for af in atlas_files:
        base = os.path.splitext(os.path.basename(af))[0]
        if base not in all_bases:
            all_bases.add(base)

    if args.names:
        selected = set(n.strip() for n in args.names.split(","))
        all_bases = all_bases & selected
        missing = selected - all_bases
        if missing:
            print(f"WARNING: Not found in source: {missing}")

    all_bases = sorted(all_bases)
    print(f"Source: {src_dir}")
    print(f"Destination: {dst_dir}")
    print(f"Textures: {tex_dir}")
    print(f"Target version: {args.version}")
    print(f"Assets to process: {len(all_bases)}\n")

    if args.dry_run:
        for base in all_bases:
            skel = "skel" if os.path.exists(os.path.join(src_dir, f"{base}.skel")) else "----"
            atlas = "atlas" if os.path.exists(os.path.join(src_dir, f"{base}.atlas")) else "-----"
            print(f"  {base}: [{skel}] [{atlas}]")
        print(f"\nDry run complete. {len(all_bases)} assets would be processed.")
        return

    converter = ensure_converter()
    os.makedirs(dst_dir, exist_ok=True)

    converted = 0
    atlas_only = 0
    failed = []
    copied_textures = set()

    for base in all_bases:
        skel_path = os.path.join(src_dir, f"{base}.skel")
        atlas_path = os.path.join(src_dir, f"{base}.atlas")

        has_skel = os.path.exists(skel_path)
        has_atlas = os.path.exists(atlas_path)

        if has_skel and has_atlas:
            with tempfile.NamedTemporaryFile(suffix=".skel", delete=False) as tmp:
                tmp_out = tmp.name

            result = subprocess.run(
                [converter, skel_path, tmp_out, "-v", args.version],
                capture_output=True, text=True
            )

            if result.returncode != 0 or not os.path.exists(tmp_out):
                print(f"  FAIL {base}: {result.stderr.strip()}")
                failed.append(base)
                if os.path.exists(tmp_out):
                    os.unlink(tmp_out)
                continue

            dst_skel = os.path.join(dst_dir, f"{base}.skel.bytes")
            shutil.move(tmp_out, dst_skel)
            converted += 1

        elif has_atlas and not has_skel:
            atlas_only += 1

        if has_atlas:
            dst_atlas = os.path.join(dst_dir, f"{base}.atlas.txt")
            shutil.copy2(atlas_path, dst_atlas)

            for tex_name in get_atlas_textures(atlas_path):
                tex_src = os.path.join(tex_dir, tex_name)
                tex_dst = os.path.join(dst_dir, tex_name)
                if tex_src not in copied_textures and os.path.exists(tex_src):
                    shutil.copy2(tex_src, tex_dst)
                    copied_textures.add(tex_src)

        if args.extract_sprites and has_skel and has_atlas:
            extract_sprites_for_asset(base, atlas_path, tex_dir, dst_dir, converter)

        total_done = converted + atlas_only
        if total_done > 0 and total_done % 20 == 0:
            print(f"  ... {total_done}/{len(all_bases)} processed")

    print(f"\n{'=' * 40}")
    print(f"Converted (skel→4.2): {converted}")
    print(f"Atlas-only (no skel): {atlas_only}")
    print(f"Textures copied: {len(copied_textures)}")
    print(f"Failed: {len(failed)}")
    if failed:
        print(f"Failed assets: {failed}")
    if args.extract_sprites:
        print(f"Sprite extraction: enabled (see Projects/ subdirectories)")
    print(f"Output: {dst_dir}")


if __name__ == "__main__":
    main()
