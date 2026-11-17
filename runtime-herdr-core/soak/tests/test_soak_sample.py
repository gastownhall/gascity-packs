from __future__ import annotations

from pathlib import Path

from soaksample import parse_cpu_stat, parse_meminfo, parse_systemctl_show, tree_bytes


def test_parsers() -> None:
    assert parse_systemctl_show("MainPID=4242\nNRestarts=3\nActiveState=active\n") == {"MainPID": "4242", "NRestarts": "3", "ActiveState": "active"}
    assert parse_cpu_stat("usage_usec 123456\nuser_usec 100\nsystem_usec 23\n") == 123456
    assert parse_cpu_stat("nothing 1\n") is None
    assert parse_meminfo("MemTotal:  8000000 kB\nMemAvailable:    6123456 kB\n") == 6123456
    assert parse_meminfo("") is None


def test_tree_bytes_counts_regular_files_without_following_links(tmp_path: Path) -> None:
    root = tmp_path / "R"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "one").write_bytes(b"x" * 100)
    (root / "a" / "b" / "two").write_bytes(b"y" * 23)
    (root / "link").symlink_to(tmp_path)
    assert tree_bytes(root) == 123
    assert tree_bytes(tmp_path / "missing") is None
