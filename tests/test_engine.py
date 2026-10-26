import tempfile
import time
import unittest
from pathlib import Path

from app.engine import Engine, Quote, SyntheticProvider, position_size


class Fixed:
    def __init__(self, quote):
        self.value = quote
    def quote(self, index, now):
        return self.value


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.sqlite3')
        self.e = Engine(self.path)
        self.now = time.time()
        self.e.control('start')

    def tearDown(self):
        self.temp.cleanup()

    def run_ticks(self, n=20):
        for i in range(n):
            self.e.step(self.now+i)

    def test_position_sizing_accounts_for_exit_slippage_and_capital(self):
        q = position_size(10000,.005,10,.1,2650,10000)
        self.assertLessEqual(q*10.1,50)
        self.assertLessEqual(q*2650,10000)
        self.assertEqual(position_size(10000,.01,10,.1,2650,0),0)

    def test_missing_stale_future_nan_quotes_refused(self):
        for q in [None,Quote('old',self.now-16,2650),Quote('future',self.now+1,2650),Quote('nan',self.now,float('nan'))]:
            self.e.provider=Fixed(q)
            self.e.step(self.now)
        s=self.e.snapshot()
        self.assertEqual(s['tick'],0)
        self.assertEqual(len(s['positions']),0)
        self.assertEqual(len(s['events']),5)

    def test_duplicate_is_idempotent_even_after_restart(self):
        self.e.provider=Fixed(Quote('same',self.now,2650))
        self.e.step(self.now)
        restarted=Engine(self.path,provider=self.e.provider)
        restarted.step(self.now+1)
        self.assertEqual(restarted.snapshot()['tick'],1)
        self.assertEqual(len(restarted.snapshot()['decisions']),1)

    def test_limit_and_risk_per_position(self):
        self.run_ticks(16)
        s=self.e.snapshot()
        self.assertTrue(s['positions'])
        self.assertLessEqual(len(s['positions']),2)
        for p in s['positions']:
            self.assertLessEqual(p['quantity']*(abs(p['entry']-p['stop'])+.1),50)

    def test_long_and_short_pnl_with_costs(self):
        for side in (1,-1):
            with self.e.connect() as db:
                db.execute('DELETE FROM positions')
                db.execute('UPDATE state SET balance=10000')
                db.execute('INSERT INTO positions(quote_key,side,quantity,entry,stop,target,opened) VALUES(?,?,?,?,?,?,?)',
                           (str(side),side,2,2650,2650-side*10,2650+side*15,self.now))
                p=db.execute('SELECT * FROM positions').fetchone()
                self.e.close_position(db,p,2650+side*20,self.now+1,'test')
            self.assertAlmostEqual(self.e.snapshot()['realized'],39.2)

    def test_stop_take_profit_and_stop_command(self):
        self.run_ticks(12)
        p=self.e.snapshot()['positions'][0]
        self.e.provider=Fixed(Quote('stop',self.now+12,p['stop']-1))
        self.e.step(self.now+12)
        self.assertEqual(self.e.snapshot()['trades'][0]['reason'],'stop-loss')
        self.e.control('stop')
        self.e.provider=Fixed(Quote('shutdown',self.now+13,2650))
        self.e.step(self.now+13)
        s=self.e.snapshot()
        self.assertEqual(s['mode'],'stopped')
        self.assertFalse(s['positions'])
        # Nouveau moteur pour exercer le take-profit.
        other=Engine(str(Path(self.temp.name)/'target.sqlite3'))
        other.control('start')
        for i in range(12): other.step(self.now+i)
        p=other.snapshot()['positions'][0]
        other.provider=Fixed(Quote('target',self.now+12,p['target']+1))
        other.step(self.now+12)
        self.assertEqual(other.snapshot()['trades'][0]['reason'],'take-profit')

    def test_daily_limit_latched_and_resets_next_utc_day(self):
        self.run_ticks(12)
        with self.e.connect() as db:
            db.execute('UPDATE state SET balance=9700')
        self.e.step(self.now+12)
        s=self.e.snapshot()
        self.assertFalse(s['positions'])
        self.assertIn('quotidienne',s['decisions'][0]['reason'])
        with self.e.connect() as db:
            db.execute('UPDATE state SET balance=10000')
        self.e.step(self.now+13)
        self.assertFalse(self.e.snapshot()['positions'])
        self.e.step(self.now+86400)
        self.assertTrue(self.e.snapshot()['positions'])

    def test_persistence_pause_and_profile_guard(self):
        self.run_ticks(12)
        before=self.e.snapshot()
        self.e.control('pause')
        self.e.step(self.now+13)
        restarted=Engine(self.path)
        after=restarted.snapshot()
        self.assertEqual(after['mode'],'paused')
        self.assertEqual(before['positions'],after['positions'])
        self.assertEqual(before['tick'],after['tick'])
        with self.assertRaises(ValueError): restarted.control('start','dynamique')
        with self.assertRaises(ValueError): Engine(self.path,spread=1)

    def test_synthetic_reproducibility_and_complete_journal(self):
        self.assertEqual(SyntheticProvider().quote(42,0).mid,SyntheticProvider().quote(42,1).mid)
        self.run_ticks(250)
        s=self.e.snapshot()
        self.assertTrue(s['trades'])
        self.assertGreaterEqual(s['max_dd'],0)
        with self.e.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM decisions').fetchone()[0],250)
            self.assertEqual(db.execute('SELECT count(*) FROM quotes').fetchone()[0],250)
        self.assertIn('synthetic-v1',s['decisions'][0]['params'])


if __name__=='__main__': unittest.main()
