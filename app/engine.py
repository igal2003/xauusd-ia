"""Paper trading uniquement : USD par once troy, quantité en onces troy."""
import json
import math
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.analysis import analyze


@dataclass(frozen=True)
class Profile:
    risk: float
    daily_loss: float
    max_positions: int
    stop: float
    reward: float = 1.5


PROFILES = {
    'prudent': Profile(.0025, .01, 1, 8),
    'equilibre': Profile(.005, .02, 2, 10),
    'dynamique': Profile(.01, .03, 3, 12),
}


@dataclass(frozen=True)
class Quote:
    key: str
    timestamp: float
    mid: float
    source: str = 'synthetic-v1'


class PriceProvider(Protocol):
    def quote(self, index: int, now: float) -> Quote | None: ...


class SyntheticProvider:
    """Même index = même prix ; horodatage de réception UTC réel."""
    def quote(self, index, now):
        price = 2650 + 22 * math.sin(index / 10) + 5 * math.sin(index / 3)
        return Quote(f'synthetic-v1:{index}', now, round(price, 2))


def position_size(equity, risk, stop_distance, exit_slippage, entry, available):
    budget = max(0, equity * risk)
    units = min(budget / (stop_distance + exit_slippage), max(0, available) / entry)
    return math.floor(units * 1000) / 1000


class Engine:
    def __init__(self, path='data/simulation.sqlite3', provider=None, spread=.6, slippage=.1):
        if not (math.isfinite(spread) and math.isfinite(slippage) and 0 <= spread <= 10 and 0 <= slippage <= 10):
            raise ValueError('Coûts invalides')
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path, self.provider = path, provider or SyntheticProvider()
        self.spread, self.slippage = spread, slippage
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT, profile TEXT, tick INTEGER, balance REAL, peak REAL, max_dd REAL, day TEXT, day_equity REAL, halt_day TEXT);
            INSERT OR IGNORE INTO state VALUES(1,'stopped','equilibre',0,10000,10000,0,'',10000,'');
            CREATE TABLE IF NOT EXISTS quotes(key TEXT PRIMARY KEY, timestamp REAL, mid REAL, source TEXT);
            CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, timestamp REAL, quote_key TEXT UNIQUE, signal TEXT, reason TEXT, params TEXT);
            CREATE TABLE IF NOT EXISTS positions(id INTEGER PRIMARY KEY, quote_key TEXT UNIQUE, side INTEGER, quantity REAL, entry REAL, stop REAL, target REAL, opened REAL, closed REAL, exit REAL, pnl REAL, reason TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, timestamp REAL, kind TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS analyses(quote_key TEXT PRIMARY KEY REFERENCES quotes(key), timestamp REAL NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY CHECK(id=1), spread REAL, slippage REAL);
            ''')
            db.execute('INSERT OR IGNORE INTO config VALUES(1,?,?)', (spread, slippage))
            config = db.execute('SELECT * FROM config').fetchone()
            if config['spread'] != spread or config['slippage'] != slippage:
                raise ValueError('Coûts différents de la session persistée : utiliser une nouvelle base')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        return db

    def event(self, db, kind, detail, now):
        db.execute('INSERT INTO events(timestamp,kind,detail) VALUES(?,?,?)', (now, kind, detail))

    def control(self, action, profile=None):
        if action not in ('start', 'pause', 'stop') or (profile is not None and profile not in PROFILES):
            raise ValueError('Commande ou profil invalide')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            s = db.execute('SELECT * FROM state').fetchone()
            if profile and profile != s['profile']:
                if s['mode'] == 'running' or db.execute('SELECT count(*) FROM positions WHERE closed IS NULL').fetchone()[0]:
                    raise ValueError('Mettre en pause et clôturer les positions avant de changer de profil')
                db.execute('UPDATE state SET profile=?', (profile,))
            # Arrêt demandé : liquidation au prochain cours frais, jamais sur un cours périmé.
            mode = {'start':'running', 'pause':'paused', 'stop':'stopping'}[action]
            db.execute('UPDATE state SET mode=?', (mode,))
            self.event(db, 'commande', f'{action}, profil={profile or s["profile"]}', time.time())

    def close_position(self, db, p, mid, now, reason):
        price = mid - p['side'] * (self.spread / 2 + self.slippage)
        pnl = (price - p['entry']) * p['side'] * p['quantity']
        db.execute('UPDATE positions SET closed=?, exit=?, pnl=?, reason=? WHERE id=? AND closed IS NULL',
                   (now, price, pnl, reason, p['id']))
        db.execute('UPDATE state SET balance=balance+?', (pnl,))
        self.event(db, 'clôture', f'Position {p["id"]}: {reason}, P&L {pnl:.2f} USD', now)

    def step(self, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            s = dict(db.execute('SELECT * FROM state').fetchone())
            if s['mode'] not in ('running', 'stopping'):
                return
            q = self.provider.quote(s['tick'], now)
            if q is None or not math.isfinite(q.mid) or q.mid <= 0 or not math.isfinite(q.timestamp) or not 0 <= now-q.timestamp <= 15:
                self.event(db, 'refus', 'Données absentes, invalides ou périmées (>15 secondes)', now)
                return
            if db.execute('SELECT 1 FROM quotes WHERE key=?', (q.key,)).fetchone():
                self.event(db, 'refus', 'Cours déjà traité : doublon ignoré', now)
                return
            db.execute('INSERT INTO quotes VALUES(?,?,?,?)', (q.key, q.timestamp, q.mid, q.source))
            db.execute('UPDATE state SET tick=tick+1')
            window = [dict(r) for r in db.execute('SELECT * FROM quotes ORDER BY rowid DESC LIMIT 60')][::-1]
            report = analyze(window)
            db.execute('INSERT INTO analyses VALUES(?,?,?)', (q.key, q.timestamp, json.dumps(report, ensure_ascii=False)))
            positions = db.execute('SELECT * FROM positions WHERE closed IS NULL').fetchall()
            for p in positions:
                mark = q.mid - p['side'] * self.spread / 2
                stop = (mark-p['stop']) * p['side'] <= 0
                target = (mark-p['target']) * p['side'] >= 0
                if stop or target or s['mode'] == 'stopping':
                    self.close_position(db, p, q.mid, now, 'arrêt' if s['mode']=='stopping' else ('stop-loss' if stop else 'take-profit'))
            positions = db.execute('SELECT * FROM positions WHERE closed IS NULL').fetchall()
            balance = db.execute('SELECT balance FROM state').fetchone()[0]
            unrealized = sum((q.mid-p['side']*(self.spread/2+self.slippage)-p['entry'])*p['side']*p['quantity'] for p in positions)
            equity = balance + unrealized
            day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
            if day != s['day']:
                # Référence avant le P&L du premier tick du jour, coût de liquidation inclus.
                previous = db.execute('SELECT mid FROM quotes WHERE key!=? ORDER BY rowid DESC LIMIT 1', (q.key,)).fetchone()
                prior_mid = previous[0] if previous else q.mid
                previous_positions = db.execute('SELECT * FROM positions WHERE closed IS NULL OR closed=?', (now,)).fetchall()
                prior_balance = balance - sum(p['pnl'] or 0 for p in previous_positions if p['closed'] == now)
                s['day_equity'] = prior_balance + sum((prior_mid-p['side']*(self.spread/2+self.slippage)-p['entry'])*p['side']*p['quantity'] for p in previous_positions)
                db.execute('UPDATE state SET day=?,day_equity=?', (day, s['day_equity']))
            profile = PROFILES[s['profile']]
            daily_pnl = equity - s['day_equity']
            blocked = s['halt_day'] == day or daily_pnl <= -s['day_equity'] * profile.daily_loss
            if blocked:
                db.execute('UPDATE state SET halt_day=?', (day,))
                for p in positions:
                    self.close_position(db, p, q.mid, now, 'limite quotidienne')
                positions = []
            prices = [r[0] for r in db.execute('SELECT mid FROM quotes ORDER BY rowid DESC LIMIT 12')][::-1]
            signal = 0 if len(prices)<12 else (1 if sum(prices[-4:])/4 > sum(prices)/12 else -1)
            reason = 'Chauffe : 12 cours requis'
            if s['mode']=='stopping':
                db.execute("UPDATE state SET mode='stopped'")
                reason = 'Simulation arrêtée, positions liquidées'
            elif blocked:
                reason = 'Limite quotidienne atteinte : ouvertures interdites'
            elif len(positions) >= profile.max_positions:
                reason = 'Limite de positions atteinte'
            elif signal:
                entry = q.mid + signal*(self.spread/2+self.slippage)
                # Budget quotidien restant et risque agrégé des stops existants.
                reserved = sum(max(0, (p['entry']-p['stop'])*p['side']+self.slippage)*p['quantity'] for p in positions)
                remaining = max(0, s['day_equity']*profile.daily_loss + daily_pnl - reserved)
                risk = min(profile.risk, remaining / max(equity, 1))
                notional = sum(p['quantity']*q.mid for p in positions)
                quantity = position_size(equity, risk, profile.stop, self.slippage, entry, equity-notional)
                if quantity >= .001:
                    db.execute('INSERT INTO positions(quote_key,side,quantity,entry,stop,target,opened) VALUES(?,?,?,?,?,?,?)',
                               (q.key,signal,quantity,entry,entry-signal*profile.stop,entry+signal*profile.stop*profile.reward,now))
                    reason = 'Achat' if signal==1 else 'Vente'; reason += ' : moyenne 4 cours contre moyenne 12 cours'
                else:
                    reason = 'Budget de risque ou capital disponible insuffisant'
            params = {**asdict(profile), 'profile':s['profile'], 'spread':self.spread, 'slippage':self.slippage, 'strategy':'sma-4-12-v1', 'source':q.source}
            db.execute('INSERT INTO decisions(timestamp,quote_key,signal,reason,params) VALUES(?,?,?,?,?)',
                       (now,q.key,str(signal),reason,json.dumps(params)))
            balance = db.execute('SELECT balance FROM state').fetchone()[0]
            positions = db.execute('SELECT * FROM positions WHERE closed IS NULL').fetchall()
            equity = balance+sum((q.mid-p['side']*(self.spread/2+self.slippage)-p['entry'])*p['side']*p['quantity'] for p in positions)
            peak = max(s['peak'],equity)
            dd = max(s['max_dd'], (peak-equity)/peak)
            db.execute('UPDATE state SET peak=?,max_dd=?', (peak,dd))

    def snapshot(self):
        with self.connect() as db:
            s = dict(db.execute('SELECT * FROM state').fetchone())
            quotes = [dict(r) for r in db.execute('SELECT * FROM quotes ORDER BY rowid DESC LIMIT 300')][::-1]
            positions = [dict(r) for r in db.execute('SELECT * FROM positions WHERE closed IS NULL')]
            mid = quotes[-1]['mid'] if quotes else None
            for p in positions:
                p['unrealized'] = (mid-p['side']*(self.spread/2+self.slippage)-p['entry'])*p['side']*p['quantity'] if mid else 0
            unrealized = sum(p['unrealized'] for p in positions)
            return {**s, 'equity':s['balance']+unrealized, 'realized':s['balance']-10000, 'unrealized':unrealized,
                    'quotes':quotes, 'positions':positions,
                    'analysis': next((json.loads(r[0]) for r in db.execute('SELECT payload FROM analyses ORDER BY rowid DESC LIMIT 1')), None),
                    'analysis_history': [json.loads(r[0]) for r in db.execute('SELECT payload FROM analyses ORDER BY rowid DESC LIMIT 10')],
                    'trades':[dict(r) for r in db.execute('SELECT * FROM positions WHERE closed IS NOT NULL ORDER BY id DESC LIMIT 100')],
                    'decisions':[dict(r) for r in db.execute('SELECT * FROM decisions ORDER BY id DESC LIMIT 100')],
                    'events':[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 50')],
                    'profiles':{k:asdict(v) for k,v in PROFILES.items()}, 'spread':self.spread,'slippage':self.slippage,
                    'data_label':'Démonstration — données simulées', 'modules':{'news':'désactivé','llm':'désactivé','daily_summary':'désactivé'}}

