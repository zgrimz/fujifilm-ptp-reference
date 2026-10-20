#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild allowlisted metadata fixtures from the two public FilmKit captures.

Original captures and complete APP1 envelopes remain in memory. The output has
new directories/offsets and only recipe numeric tags, Make/Model, ColorSpace and
InteropIndex. It is not a byte-identical camera JPEG. ExifTool must independently
report the same selected values before any fixture is written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from jpeg_recipe import NAMES, SOURCE, parse_jpeg
from ptpcap import transactions, jpeg_metadata_envelope
from generate_synthetic import make_jpeg


def oracle(data):
    names = sorted({"FujiFilm:" + name for name in NAMES.values()} |
                   {"IFD0:Make", "IFD0:Model", "ExifIFD:ColorSpace", "InteropIFD:InteropIndex"})
    run = subprocess.run(["exiftool", "-j", "-s", *["-" + name for name in names], "-"],
                         input=data, capture_output=True, check=True)
    values = json.loads(run.stdout)[0]
    values.pop("SourceFile", None)
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xt50_capture", type=Path)
    parser.add_argument("xt30_capture", type=Path)
    args = parser.parse_args()
    if subprocess.check_output(["exiftool", "-ver"], text=True).strip() != "13.55":
        raise SystemExit("Fixture derivation pins ExifTool 13.55")
    pending, cases = [], []
    for path, issue, firmware, tids in ((args.xt50_capture, 12, "1.31", (1133, 1753)),
                                      (args.xt30_capture, 13, "2.01", (215, 546))):
        tx = transactions(path, recover=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for tid in tids:
            transaction = tx[tid]
            if transaction["op"] != 0x1009:
                raise SystemExit("Selected transaction is not GetObject")
            original = jpeg_metadata_envelope(transaction["in"] or transaction["in_partial"] or b"")
            if original is None:
                raise SystemExit("No complete EXIF APP1 segment")
            result = parse_jpeg(original)
            if result["status"] != "ok":
                raise SystemExit("Capture metadata did not parse cleanly")
            tags = []
            for entry in result["raw_tags"]:
                if entry["group"] == "FujiFilm" and "value" in entry:
                    if entry["type"] in (2, 7, 11, 12):
                        raise SystemExit("Unexpected type in selected numeric recipe tag")
                    tags.append((int(entry["tag"], 16), entry["type"], entry["value"]))
            model = result["camera"]["model"]["value"]
            data = make_jpeg(tags, model=model.encode("ascii") + b"\0",
                             color_space=result["observations"]["exif_color_space"]["value"],
                             interop=result["observations"]["interop_index"]["value"].encode("ascii") + b"\0")
            expected = oracle(original)
            if oracle(data) != expected:
                raise SystemExit("Independent ExifTool values differ after sanitization")
            name = f"capture-derived-{model.lower().replace('-', '')}-tid-{tid}.jpg"
            pending.append((HERE / name, data))
            cases.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                          "model": model, "firmware_reported_by_source": firmware,
                          "source": f"https://github.com/eggricesoy/filmkit/issues/{issue}",
                          "capture_sha256": digest, "get_object_tid": tid,
                          "transfer_complete": transaction["in"] is not None,
                          "exif_app1_complete": True, "pixels_validated": False,
                          "expected": expected})
    manifest = {"schema": "jpeg-fixture-manifest/1", "evidence": "capture-derived numeric metadata",
                "derivation": "allowlisted values reserialized into new metadata-only JPEG directories; original offsets, photos, serials, timestamps and other fields are absent",
                "scope": "observed encodings only; original capture reassembly and layout require the source captures",
                "oracle": SOURCE, "oracle_comparison": "ExifTool 13.55 selected printed values match original complete APP1 and reserialized fixture",
                "generator": "derive_public_capture.py", "cases": cases}
    for path, data in pending:
        path.write_bytes(data)
    (HERE / "capture-derived-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Created {len(pending)} sanitized capture-derived metadata fixtures")


if __name__ == "__main__":
    main()
