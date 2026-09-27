import time
from pathlib import Path
from scripts.fileops import newest_file, move_into


def test_newest_file_returns_most_recent_matching_extension(tmp_path):
    older = tmp_path / "a.png"
    older.write_bytes(b"x")
    time.sleep(0.01)
    newer = tmp_path / "b.png"
    newer.write_bytes(b"y")
    (tmp_path / "note.txt").write_text("ignore")
    result = newest_file(tmp_path, exts={".png"})
    assert result == newer


def test_newest_file_respects_since_timestamp(tmp_path):
    old = tmp_path / "old.png"
    old.write_bytes(b"x")
    cutoff = time.time() + 0.005
    time.sleep(0.02)
    new = tmp_path / "new.png"
    new.write_bytes(b"y")
    result = newest_file(tmp_path, exts={".png"}, since=cutoff)
    assert result == new


def test_newest_file_returns_none_when_empty(tmp_path):
    assert newest_file(tmp_path, exts={".png"}) is None


def test_newest_file_recursive_searches_subdirs(tmp_path):
    # Codex saves to ~/.codex/generated_images/<session-uuid>/ig_*.png
    sub = tmp_path / "019e9a5b-session"
    sub.mkdir()
    img = sub / "ig_abc.png"
    img.write_bytes(b"x")
    assert newest_file(tmp_path, exts={".png"}, recursive=True) == img
    # non-recursive must NOT descend into the subdir
    assert newest_file(tmp_path, exts={".png"}) is None


def test_move_into_moves_file_and_returns_new_path(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "img.png"
    src.write_bytes(b"data")
    dest_dir = tmp_path / "work"
    moved = move_into(dest_dir, src)
    assert moved.parent == dest_dir
    assert moved.read_bytes() == b"data"
    assert not src.exists()


def test_move_into_avoids_overwriting_existing_name(tmp_path):
    dest_dir = tmp_path / "work"
    dest_dir.mkdir()
    (dest_dir / "img.png").write_bytes(b"existing")
    src = tmp_path / "img.png"
    src.write_bytes(b"new")
    moved = move_into(dest_dir, src)
    assert moved.name != "img.png"
    assert moved.read_bytes() == b"new"
    assert (dest_dir / "img.png").read_bytes() == b"existing"
