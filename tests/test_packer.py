import zipfile

import pytest

from bluekitchen.packer import PackingError, pack_zip


def test_pack_directory_into_zip(tmp_path):
    source = tmp_path / "prepared"
    (source / "META-INF" / "com" / "google" / "android").mkdir(parents=True)
    (source / "system.new.dat.br").write_bytes(b"system-data")
    (source / "META-INF" / "com" / "google" / "android" / "updater-script").write_text(
        "ui_print('prepared')", encoding="utf-8"
    )
    output = tmp_path / "prepared-rom.zip"

    result = pack_zip(source, output)

    with zipfile.ZipFile(output) as archive:
        assert archive.read("system.new.dat.br") == b"system-data"
        assert "META-INF/com/google/android/updater-script" in archive.namelist()
    assert result["files_packed"] == 2
    assert result["source_preserved"] is True


def test_refuse_to_overwrite_existing_zip(tmp_path):
    source = tmp_path / "prepared"
    source.mkdir()
    output = tmp_path / "rom.zip"
    output.write_bytes(b"keep")

    with pytest.raises(PackingError, match="already exists"):
        pack_zip(source, output)
    assert output.read_bytes() == b"keep"


def test_refuse_output_inside_source(tmp_path):
    source = tmp_path / "prepared"
    source.mkdir()

    with pytest.raises(PackingError, match="outside the source"):
        pack_zip(source, source / "rom.zip")


def test_enforce_file_limit(tmp_path):
    source = tmp_path / "prepared"
    source.mkdir()
    (source / "a").write_text("a")
    (source / "b").write_text("b")

    with pytest.raises(PackingError, match="more than 1 files"):
        pack_zip(source, tmp_path / "rom.zip", max_files=1)
    assert not (tmp_path / "rom.zip").exists()
