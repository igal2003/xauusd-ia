import json
import tempfile
import unittest
from pathlib import Path

from app.analysis import analyze
from app.engine import Engine, Quote


def observations(prices, source='synthetic-test'):
    return [dict(key=str(i), timestamp=1000+i, mid=p, source=source)
            for i, p in enumerate(prices)]


class AnalysisTests(unittest.TestCase):
    def test_warmup_and_empty(self):
        self.assertIsNone(analyze([]))
        result = analyze(observations([2600] * 19))
        self.assertFalse(result['ready'])
        self.assertEqual(result['indicators'], {})

    def test_trends_and_rsi_edges(self):
        for prices, trend, rsi in [([2600+i for i in range(20)], 'haussière', 100),
                                   ([2600-i for i in range(20)], 'baissière', 0),
                                   ([2600]*20, 'neutre', 50)]:
            result = analyze(observations(prices))
            self.assertEqual(result['trend'], trend)
            self.assertEqual(result['indicators']['rsi14_simple'], rsi)
            json.dumps(result, allow_nan=False)

    def test_simple_rsi_known_alternating_changes(self):
        prices = [2600]*6
        for i in range(14):
            prices.append(prices[-1] + (2 if i % 2 == 0 else -1))
        self.assertAlmostEqual(analyze(observations(prices))['indicators']['rsi14_simple'], 200/3)

    def test_provenance_and_invalid_prices(self):
        self.assertFalse(analyze(observations([2600]*20, 'external'))['synthetic'])
        for price in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                analyze(observations([price]*20))

    def test_archive_transaction_idempotence_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'test.sqlite3')
            engine = Engine(path)
            engine.control('start')
            for i in range(65):
                engine.step(1000+i)
            snapshot = engine.snapshot()
            report = snapshot['analysis']
            self.assertEqual(report['observations'], 60)
            self.assertEqual(report['quote_key'], snapshot['quotes'][-1]['key'])
            self.assertEqual(len(snapshot['analysis_history']), 10)
            with engine.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM analyses').fetchone()[0], 65)
            class Duplicate:
                def quote(self, index, now):
                    return Quote(report['quote_key'], now, 2600)
            engine.provider = Duplicate()
            engine.step(1065)
            self.assertEqual(engine.snapshot()['analysis'], report)
            restarted = Engine(path)
            self.assertEqual(restarted.snapshot()['analysis'], report)
            restarted.control('pause')
            restarted.step(2000)
            self.assertEqual(restarted.snapshot()['analysis'], report)

    def test_additive_schema_existing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'old.sqlite3')
            engine = Engine(path)
            engine.control('start')
            for i in range(20):
                engine.step(1000+i)
            before = engine.snapshot()
            with engine.connect() as db:
                db.execute('DROP TABLE analyses')
            restarted = Engine(path)
            after = restarted.snapshot()
            self.assertIsNone(after['analysis'])
            self.assertEqual(before['positions'], after['positions'])
            self.assertEqual(before['tick'], after['tick'])
            restarted.step(1020)
            self.assertTrue(restarted.snapshot()['analysis']['ready'])
