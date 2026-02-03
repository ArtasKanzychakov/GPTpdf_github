from dataclasses import dataclass
from typing import List


@dataclass
class NicheDetails:
    name: str
    description: str
    target_audience: str
    monetization_model: str
    complexity_level: str


@dataclass
class AnalysisResult:
    summary: str
    recommended_niches: List[NicheDetails]
    risks: List[str]
    next_steps: List[str]