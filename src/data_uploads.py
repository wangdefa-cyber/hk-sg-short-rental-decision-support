"""Validation and storage helpers for manually uploaded source files."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class UploadedFile(Protocol):
    name: str

    def getbuffer(self) -> memoryview:
        """Return the uploaded file bytes."""


def canonical_upload_name(filename: str, allowed_names) -> str | None:
    """Return the configured filename matching an upload, ignoring case."""
    lookup = {Path(name).name.casefold(): Path(name).name for name in allowed_names}
    return lookup.get(Path(filename).name.casefold())


def validate_uploads(uploaded, allowed_names) -> tuple[list[UploadedFile], list[str]]:
    """Split uploads into recognized and unrecognized filenames."""
    valid: list[UploadedFile] = []
    invalid: list[str] = []
    for item in uploaded:
        if canonical_upload_name(item.name, allowed_names) is None:
            invalid.append(item.name)
        else:
            valid.append(item)
    return valid, invalid


def save_uploads(
    uploaded,
    target_dir: Path,
    *,
    allowed_names,
    allow_overwrite: bool,
) -> tuple[list[str], list[str]]:
    """Save uploads with canonical filenames and report skipped existing files."""
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    skipped: list[str] = []
    for item in uploaded:
        canonical_name = canonical_upload_name(item.name, allowed_names)
        if canonical_name is None:
            raise ValueError(f"不支持的文件名：{item.name}")
        target = target_dir / canonical_name
        if target.exists() and not allow_overwrite:
            skipped.append(str(target))
            continue
        target.write_bytes(item.getbuffer())
        saved.append(str(target))
    return saved, skipped
