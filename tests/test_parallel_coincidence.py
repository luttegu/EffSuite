"""Scheduler tests with a synthetic external program, independent of real physics."""
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import threading
import time
import unittest

from effsuite.parallel_coincidence import (CalculationCancelled, CoincidenceError,
    SharedInputs, _publish_new, calculate_parallel, split_library)


def record(name: str, newline: bytes = b"\n") -> bytes:
    rows = [name.encode("ascii"), b"10 .5 1 .5", b"0 0 0 0 1E30",
            b"100 1 0 0 0", b"-1 0 0 0 0", b"2 1 100 1 0 0 0",
            b"-1 0 0 0 0 0 0"]
    return newline.join(rows) + newline


CURVE = b"10 .01 .009\n100 .02 .019\n1000 .005 .004\n"
LIBRARY = record("CO-60") + record("EU-152") + record("EU-152b") + record("CS-134")

FAKE = r'''import json, os, pathlib, sys, time
settings = json.loads(pathlib.Path(sys.argv[1]).read_text())
start = time.monotonic()
time.sleep(settings.get("sleep", 0))
if settings.get("fail"):
    sys.stderr.write("synthetic failure")
    sys.exit(7)
names = [line[:10].rstrip() for line in pathlib.Path("kordaten.txt").read_text().splitlines()
         if line and line[0].isalpha()]
groups = []
for name in names:
    if name.endswith("b"):
        groups[-1][1] += 1
    else:
        groups.append([name, 1])
out = []
for name, branches in groups:
    label = "WRONG" if settings.get("bad_label") else name
    out.append(f"{label:<10}{100:10d}{1.0 + branches / 10:15.3f}\n")
pathlib.Path("coin.txt").write_text("".join(out))
if settings.get("trace"):
    with open(settings["trace"], "a") as trace:
        trace.write(json.dumps({"pid": os.getpid(), "start": start, "end": time.monotonic(),
                                "cwd": str(pathlib.Path.cwd())}) + "\n")
'''


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        script = self.root / "synthetic.py"
        script.write_text(FAKE)
        self.settings = self.root / "settings.json"
        self.settings.write_text("{}")
        self.command = (str(Path(sys.executable).resolve()), str(script), str(self.settings))
        self.inputs = SharedInputs(CURVE, CURVE, LIBRARY)

    def tearDown(self):
        self.directory.cleanup()

    def test_parent_and_continuation_bytes_stay_together(self):
        groups = split_library(LIBRARY)
        self.assertEqual([g.name for g in groups], ["CO-60", "EU-152", "CS-134"])
        self.assertEqual(groups[1].records, ("EU-152", "EU-152b"))
        self.assertEqual(b"".join(group.raw for group in groups), LIBRARY)

    def test_crlf_bytes_are_preserved(self):
        library = record("CO-60", b"\r\n") + record("CO-60b", b"\r\n")
        self.assertEqual(split_library(library)[0].raw, library)

    def test_orphan_continuation_is_rejected(self):
        with self.assertRaisesRegex(CoincidenceError, "no preceding"):
            split_library(record("EU-152b"))

    def test_truncated_record_is_rejected(self):
        with self.assertRaises(CoincidenceError):
            split_library(LIBRARY[:-20])

    def test_serial_parallel_byte_identity_and_original_order(self):
        serial = calculate_parallel(self.inputs, self.command, workers=1)
        parallel = calculate_parallel(self.inputs, self.command, workers=3, verify_serial=True)
        self.assertEqual(serial.coin_bytes, parallel.coin_bytes)
        self.assertTrue(parallel.report["serial_verification"]["passed"])
        self.assertEqual([line[:10].strip() for line in parallel.coin_bytes.splitlines()],
                         [b"CO-60", b"EU-152", b"CS-134"])
        self.assertIn(b"1.200", parallel.coin_bytes)  # EU's two records accumulated.

    def test_multiple_native_processes_overlap_and_use_private_directories(self):
        trace = self.root / "trace.ndjson"
        self.settings.write_text(json.dumps({"sleep": .2, "trace": str(trace)}))
        result = calculate_parallel(self.inputs, self.command, workers=3)
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertEqual(result.report["workers"], 3)
        self.assertEqual(len({e["pid"] for e in events}), 3)
        self.assertEqual(len({e["cwd"] for e in events}), 3)
        self.assertLess(max(e["start"] for e in events), min(e["end"] for e in events))

    def test_selection_uses_complete_parent_group(self):
        result = calculate_parallel(self.inputs, self.command, workers=8, nuclides=("eu-152",))
        self.assertEqual(result.report["workers"], 1)
        self.assertEqual(result.report["decay_records"], 2)
        self.assertEqual(len(result.coin_bytes.splitlines()), 1)
        self.assertIn(b"1.200", result.coin_bytes)

    def test_cannot_select_continuation_as_an_independent_nuclide(self):
        with self.assertRaisesRegex(CoincidenceError, "Unknown parent"):
            calculate_parallel(self.inputs, self.command, nuclides=("EU-152b",))

    def test_partial_nuclides_calculates_available_and_reports_missing(self):
        result = calculate_parallel(self.inputs, self.command, workers=2, nuclides=("CO-60", "UNKNOWN-99", "RA-223"))
        self.assertEqual(len(result.coin_bytes.splitlines()), 1)
        self.assertIn(b"CO-60", result.coin_bytes)
        self.assertEqual(result.report["missing_nuclides"], ["RA-223", "UNKNOWN-99"])

    def test_progress_counts_parent_groups(self):
        updates = []
        calculate_parallel(self.inputs, self.command, workers=2,
                           progress=lambda *args: updates.append(args))
        self.assertEqual([entry[0] for entry in updates], [1, 2, 3])
        self.assertEqual({entry[2] for entry in updates}, {"CO-60", "EU-152", "CS-134"})

    def test_bad_curve_grid_is_rejected_before_execution(self):
        inputs = SharedInputs(CURVE, CURVE.replace(b"100 ", b"101 "), LIBRARY)
        with self.assertRaisesRegex(CoincidenceError, "grids must match"):
            calculate_parallel(inputs, self.command)

    def test_cancel_before_start(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(CalculationCancelled):
            calculate_parallel(self.inputs, self.command, cancel=event)

    def test_cancel_running_workers(self):
        self.settings.write_text(json.dumps({"sleep": 3}))
        event = threading.Event()
        timer = threading.Timer(.15, event.set)
        timer.start()
        started = time.monotonic()
        try:
            with self.assertRaises(CalculationCancelled):
                calculate_parallel(self.inputs, self.command, workers=3, cancel=event)
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - started, 2)

    def test_timeout_does_not_return_partial_results(self):
        self.settings.write_text(json.dumps({"sleep": 3}))
        with self.assertRaisesRegex(CoincidenceError, "exceeded"):
            calculate_parallel(self.inputs, self.command, workers=2, timeout_seconds=.1)

    def test_native_failure_is_reported(self):
        self.settings.write_text(json.dumps({"fail": True}))
        with self.assertRaisesRegex(CoincidenceError, "exit 7"):
            calculate_parallel(self.inputs, self.command, workers=2)

    def test_unexpected_output_label_is_rejected(self):
        self.settings.write_text(json.dumps({"bad_label": True}))
        with self.assertRaisesRegex(CoincidenceError, "Unexpected nuclide"):
            calculate_parallel(self.inputs, self.command, workers=2)

    def test_publish_preserves_an_existing_lab_file(self):
        path = self.root / "coin.txt"
        path.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            _publish_new(path, b"replacement")
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(list(self.root.glob(".cascade-*")), [])

    def test_publish_exposes_complete_bytes(self):
        path = self.root / "coin.txt"
        _publish_new(path, b"complete result\n")
        self.assertEqual(path.read_bytes(), b"complete result\n")


if __name__ == "__main__":
    unittest.main()
