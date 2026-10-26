"""Contrats futurs : aucun fournisseur connecté ni nouvelle réelle inventée."""
from dataclasses import dataclass
from typing import Protocol, Sequence
from app.engine import Quote


@dataclass(frozen=True)
class EconomicItem:
    title: str
    source_url: str
    published_at: str
    retrieved_at: str


class EconomicProvider(Protocol):
    def items(self) -> Sequence[EconomicItem]: ...


class AnalysisProvider(Protocol):
    def analyze(self, quotes: Sequence[Quote], news: Sequence[EconomicItem]) -> str: ...


class DailySummaryProvider(Protocol):
    def summarize(self, date_utc: str, decisions: Sequence[dict], trades: Sequence[dict]) -> str: ...


@dataclass(frozen=True)
class StrategyEvaluation:
    strategy_version: str
    dataset_id: str
    split: str  # calibration / validation / test, sans chevauchement
    synthetic: bool
    metrics: dict

# Ces interfaces ne donnent aucun accès aux commandes ni aux limites du moteur.
