# SPDX-License-Identifier: MIT
"""The stray-file check names what .gitignore keeps out of the record; local tooling is never scanned."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("check_reference", Path(__file__).resolve().parents[1] / "tools" / "check_reference.py")
check_reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_reference)

# One file for every pattern the record's .gitignore names, each where a run or an export would leave it.
STRAYS = (
    "captures/run.pcap", "captures/run.pcapng", "captures/run.pcap.gz", "captures/run.pcapng.gz",
    "fixtures/DSCF0001.RAF", "fixtures/dscf0002.raf", "fixtures/DSCF0003.Raf",
    "bankprobe-20261019-120000.json", "tools/bankprobe-run.txt", "backups/bankprobe-X-T50-C7-20261019.json",
    "tools/__pycache__/ptpcap.cpython-313.pyc", "docs/.DS_Store",
)
# Files that belong in the record and share a stem, suffix fragment or directory with a stray.
KEPT = ("README.md", "tools/ptpcap.py", "evidence/report.json", "captures/transcript.txt", "fixtures/jpeg/sample.jpg",
        "docs/bankprobe.md", "captures/notes-on-pcap.md")


def touch(root, relative):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return Path(relative)


class StrayArtifactsTest(unittest.TestCase):
    def test_reports_every_pattern_gitignore_names_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strays = [touch(root, relative) for relative in STRAYS]
            for relative in KEPT:
                touch(root, relative)
            self.assertEqual(check_reference.stray_artifacts(root), sorted(strays))

    def test_never_looks_inside_local_tooling_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root, ".venv/lib/python3.13/site-packages/jsonschema/__pycache__/validators.cpython-313.pyc")
            touch(root, "venv/lib/python3.13/site-packages/README.md")
            touch(root, ".pytest_cache/README.md")
            touch(root, ".obsidian/workspace.json")
            touch(root, ".git/objects/ab/cdef0123")
            kept = touch(root, "docs/index.md")
            self.assertEqual(check_reference.record_files(root), [kept])
            self.assertEqual(check_reference.stray_artifacts(root), [])

    def test_check_reports_a_stray_in_the_json_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root, "README.md")
            stray = touch(root, "captures/run.pcapng.gz")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                status = check_reference.check(root)
            summary = json.loads(out.getvalue())
            self.assertEqual(status, 1)
            self.assertEqual(summary["markdown_files"], 1)
            self.assertEqual(summary["errors"], [f"export artifact should be excluded: {stray}"])


if __name__ == "__main__":
    unittest.main()
