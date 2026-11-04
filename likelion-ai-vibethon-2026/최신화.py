#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""프로젝트의 읽을 수 있는 소스 코드만 UTF-8 텍스트로 모은다."""

import os
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional, Tuple


ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = ROOT / "프로젝트.txt"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}
EXCLUDE_FILES = {"프로젝트.txt", "최신화.py", ".DS_Store"}

# 바이너리를 뒤늦게 걸러내는 대신, 프로젝트 공유에 필요한 텍스트 형식만 허용한다.
TEXT_EXTENSIONS = {
    ".bat",
    ".command",
    ".css",
    ".csv",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {"Dockerfile", "Makefile", ".gitignore"}
VISIBLE_HIDDEN_FILES = {".env.example", ".gitignore"}


def normalized(value: str) -> str:
    """macOS의 NFD 한글 파일명도 비교·출력할 때 NFC로 통일한다."""
    return unicodedata.normalize("NFC", value)


def should_include(file_path: Path) -> bool:
    parts = {normalized(part) for part in file_path.relative_to(ROOT).parts}
    name = normalized(file_path.name)

    if parts & EXCLUDE_DIRS or name in EXCLUDE_FILES:
        return False
    if name.startswith(".") and name not in VISIBLE_HIDDEN_FILES:
        return False
    return name in TEXT_FILENAMES or file_path.suffix.lower() in TEXT_EXTENSIONS


def read_text_safely(file_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """UTF-8을 우선 사용하고, 실제 CP949 텍스트만 보조적으로 복구한다."""
    raw = file_path.read_bytes()
    if b"\x00" in raw[:8192]:
        return None, "바이너리 데이터"

    for encoding in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(encoding)
            # 모든 줄바꿈을 LF로 맞춰 다른 OS에서도 글자가 안정적으로 보이게 한다.
            return text.replace("\r\n", "\n").replace("\r", "\n"), encoding
        except UnicodeDecodeError:
            continue
    return None, "지원하지 않는 문자 인코딩"


def write_atomically(text: str) -> None:
    """생성 도중 실패해도 기존 결과가 반쯤 덮어써지지 않게 한다."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=ROOT,
            prefix=".project-export-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(text)
        os.replace(temp_path, OUTPUT_FILE)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def generate_smart_txt() -> None:
    sections = []
    included_count = 0
    skipped_count = 0
    print("[*] 프로젝트의 텍스트 소스를 UTF-8로 모으는 중...")

    for file_path in sorted(ROOT.rglob("*")):
        if not file_path.is_file() or not should_include(file_path):
            continue

        try:
            code_text, detected = read_text_safely(file_path)
        except OSError as error:
            print(f"[건너뜀] {file_path.name}: {error}")
            skipped_count += 1
            continue

        if code_text is None:
            print(f"[건너뜀] {file_path.name}: {detected}")
            skipped_count += 1
            continue

        rel_path = normalized(file_path.relative_to(ROOT).as_posix())
        print(f"[포함] {rel_path} ({detected})")
        sections.append(f"{rel_path}\n`````\n{code_text.rstrip()}\n`````\n")
        included_count += 1

    header = (
        "# 프로젝트 소스 모음\n"
        "# UTF-8 / LF 형식으로 자동 생성되었습니다.\n"
        "# 실행 파일이 아니라 코드 검토·전달용 문서입니다.\n\n"
    )
    write_atomically(header + "\n".join(sections))
    print(
        f"\n[성공] {OUTPUT_FILE.name}: {included_count}개 파일 포함, "
        f"{skipped_count}개 판독 불가 파일 제외"
    )


if __name__ == "__main__":
    generate_smart_txt()
