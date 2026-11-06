from zipfile import ZipFile

from bluekitchen.inspector import inspect_zip


def test_inspect_android_rom_zip(tmp_path):
    archive = tmp_path / "rom.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("payload.bin", b"payload")
        zip_file.writestr("META-INF/com/google/android/update-binary", b"installer")
        zip_file.writestr("system/build.prop", b"ro.build.version.release=15")

    result = inspect_zip(archive)

    assert result["format"] == "zip"
    assert result["entries"] == 3
    assert "A/B OTA payload" in result["android_markers"]
    assert "Recovery installer" in result["android_markers"]
    assert result["unsafe_paths"] == []


def test_detect_unsafe_paths(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../outside.txt", "not extracted")

    result = inspect_zip(archive)
    assert result["unsafe_paths"] == ["../outside.txt"]


def test_preview_is_bounded(tmp_path):
    archive = tmp_path / "many.zip"
    with ZipFile(archive, "w") as zip_file:
        for index in range(205):
            zip_file.writestr(f"file-{index}.txt", "x")

    result = inspect_zip(archive)
    assert len(result["entries_preview"]) == 200
    assert result["preview_truncated"] is True
