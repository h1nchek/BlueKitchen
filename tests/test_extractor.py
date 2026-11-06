from zipfile import ZipFile

import pytest

from bluekitchen.extractor import ExtractionError, extract_zip


def test_extract_zip_to_new_directory(tmp_path):
    archive = tmp_path / "rom.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("payload.bin", b"payload")
        zip_file.writestr("META-INF/com/google/android/updater-script", b"ui_print")

    output = tmp_path / "unpacked"
    result = extract_zip(archive, output)

    assert (output / "payload.bin").read_bytes() == b"payload"
    assert (output / "META-INF/com/google/android/updater-script").read_bytes() == b"ui_print"
    assert result["files_extracted"] == 2
    assert result["source_preserved"] is True


def test_reject_traversal_without_creating_output(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../outside.txt", b"no")

    output = tmp_path / "unpacked"
    with pytest.raises(ExtractionError, match="Unsafe archive path"):
        extract_zip(archive, output)
    assert not output.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_reject_existing_destination(tmp_path):
    archive = tmp_path / "rom.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("system.img", b"data")
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(ExtractionError, match="already exists"):
        extract_zip(archive, output)


def test_reject_oversized_entry_before_extraction(tmp_path):
    archive = tmp_path / "large.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("system.img", b"x" * 20)

    output = tmp_path / "unpacked"
    with pytest.raises(ExtractionError, match="size limit"):
        extract_zip(archive, output, max_file_size=10)
    assert not output.exists()
