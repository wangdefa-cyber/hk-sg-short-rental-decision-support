"""Tests for fixed-name upload validation and storage."""

from __future__ import annotations

from src.data_uploads import canonical_upload_name, save_uploads, validate_uploads


class FakeUpload:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getbuffer(self) -> memoryview:
        return memoryview(self._data)


def test_canonical_upload_name_is_case_insensitive():
    allowed = {"listings.csv.gz", "calendar.csv.gz"}

    assert canonical_upload_name("Listings.CSV.GZ", allowed) == "listings.csv.gz"
    assert canonical_upload_name("unknown.csv", allowed) is None


def test_validate_uploads_separates_recognized_names():
    allowed = {"hk_travel.csv", "sg_travel.csv"}
    valid_upload = FakeUpload("HK_TRAVEL.csv", b"data")
    invalid_upload = FakeUpload("travel.csv", b"data")

    valid, invalid = validate_uploads([valid_upload, invalid_upload], allowed)

    assert valid == [valid_upload]
    assert invalid == ["travel.csv"]


def test_save_uploads_uses_canonical_name_and_skips_existing(tmp_path):
    target = tmp_path / "listings.csv.gz"
    target.write_bytes(b"existing")
    upload = FakeUpload("LISTINGS.CSV.GZ", b"new")

    saved, skipped = save_uploads(
        [upload],
        tmp_path,
        allowed_names={"listings.csv.gz"},
        allow_overwrite=False,
    )

    assert saved == []
    assert skipped == [str(target)]
    assert target.read_bytes() == b"existing"
    assert len(list(tmp_path.iterdir())) == 1


def test_save_uploads_overwrites_with_canonical_name(tmp_path):
    target = tmp_path / "listings.csv.gz"
    target.write_bytes(b"existing")
    upload = FakeUpload("Listings.CSV.GZ", b"new")

    saved, skipped = save_uploads(
        [upload],
        tmp_path,
        allowed_names={"listings.csv.gz"},
        allow_overwrite=True,
    )

    assert saved == [str(target)]
    assert skipped == []
    assert target.read_bytes() == b"new"
