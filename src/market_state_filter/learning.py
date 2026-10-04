"""Purged temporal split; model fit excludes immature / future labels."""
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score

class LineQualityModel:
    def __init__(self):
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=7))
        self.duration_model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        self.fitted_at = None

    def fit(self, records, as_of):
        eligible = [r for r in records if r["label_available_at"] < as_of]
        y = [r["survived_horizon"] for r in eligible]
        if len(eligible) < 20 or len(set(y)) < 2:
            raise ValueError("INSUFFICIENT: need >=20 mature training samples and both classes")
        self.model.fit([r["line"].features for r in eligible], y)
        self.duration_model.fit([r["line"].features for r in eligible], [r["effective_bars"] for r in eligible])
        self._training_positive_rate = float(np.mean(y))
        self.duration_cap = max(r["label_available_at"]-r["feature_at"] for r in eligible)
        self.fitted_at = as_of
        self.training_count = len(eligible)
        self.last_training_label_at = max(r["label_available_at"] for r in eligible)
        return self

    def score(self, line):
        if self.fitted_at is None:
            raise ValueError("Model is not fitted")
        if line.discovered_at < self.fitted_at:
            raise ValueError("No retrospective use of a model trained later than the line")
        return float(self.model.predict_proba([line.features])[0, 1])

    def duration_estimate(self, line):
        self.score(line)  # same temporal guard
        return float(np.clip(self.duration_model.predict([line.features])[0], 1, self.duration_cap))

    def evaluate(self, records):
        test = [r for r in records if r["feature_at"] >= self.fitted_at]
        if not test:
            raise ValueError("INSUFFICIENT: empty temporal holdout")
        y = np.array([r["survived_horizon"] for r in test]);p = np.array([self.score(r["line"]) for r in test])
        return {"train_count": self.training_count, "holdout_count": len(test),
            "last_training_label_at": self.last_training_label_at, "holdout_start": self.fitted_at,
            "brier": float(brier_score_loss(y,p)),
            "constant_baseline_brier": float(brier_score_loss(y,np.full(len(y),self.training_positive_rate))),
            "capped_duration_mae": float(np.mean([abs(self.duration_estimate(r["line"])-r["effective_bars"]) for r in test])),
            "auc": float(roc_auc_score(y,p)) if len(set(y)) == 2 else None,
            "holdout_survival_rate": float(y.mean())}

    @property
    def training_positive_rate(self):
        return self._training_positive_rate


def train_quality_model(records, split_index):
    model = LineQualityModel().fit(records, split_index)
    eligible = [r for r in records if r["label_available_at"] < split_index]
    model._training_positive_rate = float(np.mean([r["survived_horizon"] for r in eligible]))
    return model
