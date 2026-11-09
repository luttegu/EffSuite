"""Separate-stage scheduling checks; synthetic stages contain no physics."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from effsuite.parallel_coincidence import CalculationCancelled, CoincidenceError
from effsuite.well_parallel import STAGES, WellInputs, calculate_well_parallel

DECAY = (b"10 .5 1 .5\n0 0 0 0 1E30\n100 1 0 0 0\n"
         b"-1 0 0 0 0\n2 1 100 1 0 0 0\n")
CURVE = b"10 .01 .009\n100 .02 .019\n1000 .005 .004\n"
SCRIPT = '''import json, os, pathlib, sys, time
stage = sys.argv[1]
settings = json.loads(pathlib.Path(sys.argv[2]).read_text())
if stage == settings.get('fail'):
    sys.stderr.write('stage failed')
    sys.exit(7)
if stage == 'initialize':
    time.sleep(settings.get('sleep', 0))
    pathlib.Path('branches.txt').write_text('0')
elif stage == 'peak':
    p = pathlib.Path('branches.txt')
    p.write_text(str(int(p.read_text())+1))
elif stage == 'correct':
    n = int(pathlib.Path('branches.txt').read_text())
    for filename, value in [('emissions.txt', .2*n), ('peak.txt', .1*n), ('emissions2.txt', .2*n)]:
        pathlib.Path(filename).write_text(''.join(f'{i} {value if i==100 else 0}\\n' for i in range(1,3001)))
    pathlib.Path('correct.txt').write_text('100 2.0\\n')
if settings.get('trace'):
    with open(settings['trace'], 'a') as out:
        out.write(json.dumps({'cwd': str(pathlib.Path.cwd()), 'stage': stage, 'pid': os.getpid()})+'\\n')
'''


class WellParallelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.script = self.root / "stages.py"
        self.script.write_text(SCRIPT)
        self.settings = self.root / "settings.json"
        self.settings.write_text("{}")
        self.commands = {stage: (str(Path(sys.executable).resolve()), str(self.script), stage,
                                  str(self.settings)) for stage in STAGES}
        self.inputs = WellInputs(CURVE, CURVE, b"10.\n",
                                 (("CO-60", (DECAY,)), ("EU-152", (DECAY, DECAY))))

    def tearDown(self):
        self.temporary.cleanup()

    def test_parallel_and_serial_outputs_match_with_branch_accumulation(self):
        result = calculate_well_parallel(self.inputs, self.commands, workers=2, verify_serial=True)
        self.assertTrue(result.report["serial_verification"]["passed"])
        self.assertEqual(result.report["decay_records"], 3)
        self.assertEqual([name for name, _ in result.nuclides], ["CO-60", "EU-152"])
        self.assertEqual([item["corrections"][0]["numerator"] for item in result.report["nuclides"]],
                         [.2, .4])

    def test_all_stages_for_a_parent_share_one_private_directory(self):
        trace = self.root / "trace.jsonl"
        self.settings.write_text(json.dumps({"trace": str(trace)}))
        calculate_well_parallel(self.inputs, self.commands, workers=2)
        rows = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
        self.assertEqual(len({row["cwd"] for row in rows}), 2)
        self.assertEqual(sorted(sum(row["stage"] == "peak" for row in rows if row["cwd"] == directory)
                                for directory in {row["cwd"] for row in rows}), [1, 2])

    def test_stage_failure_returns_no_partial_result(self):
        self.settings.write_text('{"fail":"emissions"}')
        with self.assertRaisesRegex(CoincidenceError, "exit 7"):
            calculate_well_parallel(self.inputs, self.commands, workers=2)

    def test_timeout_stops_stage(self):
        self.settings.write_text('{"sleep": 2}')
        with self.assertRaisesRegex(CoincidenceError, "exceeded"):
            calculate_well_parallel(self.inputs, self.commands, workers=2, timeout_seconds=.1)

    def test_cancellation_is_respected(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(CalculationCancelled):
            calculate_well_parallel(self.inputs, self.commands, cancel=stop)

    def test_unknown_nuclide_never_uses_a_previous_result(self):
        with self.assertRaises(OSError):
            WellInputs.from_directories(self.root, self.root, ("MISSING",))

    def test_bad_decay_indices_are_rejected_before_execution(self):
        bad = DECAY.replace(b"2 1 100", b"101 1 100")
        with self.assertRaisesRegex(CoincidenceError, "bounds"):
            calculate_well_parallel(replace(self.inputs, groups=(("CO-60", (bad,)),)), self.commands)

    def test_parent_continuation_cannot_be_selected_as_parent(self):
        with self.assertRaisesRegex(CoincidenceError, "Invalid parent"):
            WellInputs.from_directories(self.root, self.root, ("EU-152b",))
