"""Analyse descriptive déterministe ; aucune prévision ni commande de trading."""
import math
from statistics import mean, pstdev

VERSION = 'technical-observations-v1'


def analyze(quotes):
    """Observations ordonnées, pas des bougies : fenêtres exprimées en cours."""
    if not quotes:
        return None
    prices = [q['mid'] for q in quotes]
    if any(not math.isfinite(p) or p <= 0 for p in prices):
        raise ValueError('Prix invalides pour l’analyse')
    sources = sorted({q['source'] for q in quotes})
    latest = quotes[-1]
    result = {
        'version': VERSION, 'quote_key': latest['key'],
        'timestamp': latest['timestamp'], 'sources': sources,
        'synthetic': all(s.startswith('synthetic-') for s in sources),
        'observations': len(prices), 'window_start': quotes[0]['timestamp'],
        'ready': len(prices) >= 20, 'trend': 'insuffisant',
        'indicators': {}, 'notes': [],
        'limitations': 'Analyse de cours observés, sans bougies ni horizon fixe. '
                        'Aucune actualité intégrée, aucune probabilité de gain estimée. '
                        'Cette analyse ne commande pas le moteur de trading.',
    }
    if not result['ready']:
        result['notes'] = [f'Chauffe : {len(prices)}/20 observations nécessaires.']
        return result
    fast, slow = mean(prices[-5:]), mean(prices[-20:])
    gap = (fast / slow - 1) * 100
    trend = 'haussière' if gap > .02 else 'baissière' if gap < -.02 else 'neutre'
    changes = [b - a for a, b in zip(prices[-15:-1], prices[-14:])]
    gain = mean(max(c, 0) for c in changes)
    loss = mean(max(-c, 0) for c in changes)
    rsi = 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    recent = prices[-20:]
    returns = [(b / a - 1) * 100 for a, b in zip(recent, recent[1:])]
    result['trend'] = trend
    result['indicators'] = {
        'sma5': fast, 'sma20': slow, 'gap_pct': gap,
        'rsi14_simple': rsi, 'volatility_pct': pstdev(returns),
        'range_low': min(recent), 'range_high': max(recent),
        'change_pct': (prices[-1] / prices[-20] - 1) * 100,
    }
    momentum = 'fortement positif' if rsi >= 70 else 'fortement négatif' if rsi <= 30 else 'intermédiaire'
    result['notes'] = [
        f'Tendance {trend} : moyenne 5 cours {fast:.2f}, moyenne 20 cours {slow:.2f} USD/oz.',
        f'Momentum {momentum} : RSI simple sur 14 variations = {rsi:.1f}/100. '
        'Un extrême ne garantit pas un retournement.',
        f'Fourchette des 20 derniers cours : {min(recent):.2f} à {max(recent):.2f} USD/oz ; '
        'ces bornes observées ne constituent pas des supports/résistances validés.',
        f'Volatilité par observation : {pstdev(returns):.4f} % '
        '(écart-type des rendements, non annualisé).',
    ]
    return result
