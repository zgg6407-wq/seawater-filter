"""Public pivot-pair baseline; no private market-state classifier."""
from dataclasses import dataclass, asdict
import numpy as np
from .data import atr_series

@dataclass(frozen=True)
class Pivot:
    index: int
    confirmed_at: int
    price: float
    side: str

@dataclass(frozen=True)
class CandidateLine:
    line_id: str
    side: str
    anchor1: int
    anchor2: int
    price1: float
    price2: float
    discovered_at: int
    atr: float
    features: tuple

    def value(self, index):
        return self.price2 + (self.price2-self.price1)/(self.anchor2-self.anchor1)*(index-self.anchor2)

    def record(self):
        return asdict(self)

FEATURE_NAMES = ["slope_atr", "anchor_span", "confirmation_delay", "distance_atr", "past_touch_ratio", "past_breach_ratio"]

def discover_lines(bars, left=3, right=3, max_pairs=3):
    if left < 1 or right < 1 or max_pairs < 1:
        raise ValueError("Pivot windows and max_pairs must be positive")
    atr = atr_series(bars)
    pivots = {"support": [], "resistance": []}
    candidates = []
    for confirmed in range(left+right, len(bars)):
        k = confirmed-right
        for side, column in [("support", "low"), ("resistance", "high")]:
            values = bars[column].to_numpy()
            window = values[k-left:k+right+1]
            extreme = window.min() if side == "support" else window.max()
            if values[k] != extreme or np.count_nonzero(window == extreme) != 1:
                continue
            pivot = Pivot(k, confirmed, float(values[k]), side)
            for previous in pivots[side][-max_pairs:]:
                span = k-previous.index
                slope = (pivot.price-previous.price)/span
                a = max(float(atr[confirmed]), 1e-9)
                indices = np.arange(previous.index, confirmed+1)
                projected = previous.price+slope*(indices-previous.index)
                observed = values[previous.index:confirmed+1]
                distance = np.abs(observed-projected)/a
                closes = bars.close.to_numpy()[previous.index:confirmed+1]
                breach = closes < projected-.5*a if side == "support" else closes > projected+.5*a
                now_value = pivot.price+slope*(confirmed-k)
                features = (slope/a, float(span), float(right),
                    abs(float(bars.close.iloc[confirmed])-now_value)/a,
                    float(np.mean(distance <= .5)), float(np.mean(breach)))
                candidates.append(CandidateLine(f"{side}-{previous.index}-{k}", side,
                    previous.index, k, previous.price, pivot.price, confirmed, a, features))
            pivots[side].append(pivot)
    return candidates

def mature_labels(bars, lines, horizon=24, tolerance=.5):
    if horizon < 1 or tolerance <= 0:
        raise ValueError("Invalid label configuration")
    records = []
    for line in lines:
        start = line.discovered_at
        if start+horizon >= len(bars):
            continue  # immature samples are never assigned a fake negative label
        first_failure = None
        touches = 0
        for i in range(start+1, start+horizon+1):
            row = bars.iloc[i];level = line.value(i);band = tolerance*line.atr
            if row.low <= level+band and row.high >= level-band:
                touches += 1
            failed = row.close < level-band if line.side == "support" else row.close > level+band
            if failed and first_failure is None:
                first_failure = i-start
        survival = first_failure if first_failure is not None else horizon
        records.append({"line": line, "feature_at": start, "label_available_at": start+horizon,
            "survived_horizon": int(first_failure is None), "effective_bars": survival,
            "right_censored": first_failure is None, "future_touches": touches})
    return records
