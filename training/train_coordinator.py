"""
RESCUE-AI — Train the lightweight Coordinator Decision Model.

Reads the training data produced by ``generate_dataset.py`` and fits two
scikit-learn models:

* **Priority classifier** — predicts dispatch priority (LOW / MEDIUM / HIGH / CRITICAL)
* **Dispatch regressor** — predicts how many ambulances to send

Models are persisted with ``joblib`` into ``training/trained_model/``.

Run:
    python -m training.generate_dataset          # generate data first
    python -m training.train_coordinator          # then train
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

BASE_DIR = Path(__file__).resolve().parent


def train_model(
    data_path: str | Path | None = None,
    model_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Train coordinator models and save them.

    Returns a dict of evaluation metrics.
    """
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        f1_score,
        mean_absolute_error,
    )
    import joblib

    # ---- paths ----
    if data_path is None:
        data_path = BASE_DIR / "training_data.json"
    data_path = Path(data_path)

    if model_dir is None:
        model_dir = BASE_DIR / "trained_model"
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    # ---- load ----
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    features = np.array(raw["features"], dtype=np.float32)
    labels = raw["labels"]

    priority_labels = np.array([l["priority_label"] for l in labels], dtype=int)
    dispatch_labels = np.array([l["num_dispatched"] for l in labels], dtype=float)

    print(f"Loaded {len(features)} samples, {features.shape[1]} features")

    # ---- split ----
    X_train, X_test, y_pri_train, y_pri_test, y_dis_train, y_dis_test = (
        train_test_split(
            features,
            priority_labels,
            dispatch_labels,
            test_size=0.20,
            random_state=42,
            stratify=priority_labels,
        )
    )

    # ---- priority classifier ----
    print("\nTraining priority classifier...")
    priority_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1,
    )
    priority_model.fit(X_train, y_pri_train)

    y_pri_pred = priority_model.predict(X_test)
    pri_accuracy = accuracy_score(y_pri_test, y_pri_pred)
    pri_f1 = f1_score(y_pri_test, y_pri_pred, average="weighted")

    severity_names = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    present_labels = sorted(set(y_pri_test) | set(y_pri_pred))
    target_names = [severity_names[i] for i in present_labels]

    print(f"  Accuracy : {pri_accuracy:.4f}")
    print(f"  F1 (wtd) : {pri_f1:.4f}")
    print(
        classification_report(
            y_pri_test,
            y_pri_pred,
            labels=present_labels,
            target_names=target_names,
        )
    )

    # ---- dispatch regressor ----
    print("Training dispatch count regressor...")
    dispatch_model = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1,
    )
    dispatch_model.fit(X_train, y_dis_train)

    y_dis_pred = dispatch_model.predict(X_test)
    dis_mae = mean_absolute_error(y_dis_test, y_dis_pred)
    print(f"  MAE : {dis_mae:.4f}")

    # ---- save ----
    pri_path = model_dir / "priority_model.joblib"
    dis_path = model_dir / "dispatch_model.joblib"
    joblib.dump(priority_model, pri_path)
    joblib.dump(dispatch_model, dis_path)
    print(f"\nModels saved to {model_dir}")

    # ---- feature importance ----
    feature_names = [
        "severity_enc", "num_casualties", "num_severe", "num_non_severe",
        "als_required", "bls_required", "num_avail_ambulances",
        "num_als_avail", "num_bls_avail", "min_amb_eta", "avg_amb_eta",
        "num_avail_hospitals", "min_hosp_eta", "best_trauma_level",
        "max_hosp_capacity",
    ]
    imp = priority_model.feature_importances_
    ranked = sorted(zip(feature_names, imp), key=lambda x: x[1], reverse=True)
    print("\nPriority model — top features:")
    for name, importance in ranked[:8]:
        print(f"  {name:28s}  {importance:.4f}")

    return {
        "priority_accuracy": round(pri_accuracy, 4),
        "priority_f1_weighted": round(pri_f1, 4),
        "dispatch_mae": round(dis_mae, 4),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "feature_count": features.shape[1],
        "priority_model_path": str(pri_path),
        "dispatch_model_path": str(dis_path),
    }


if __name__ == "__main__":
    metrics = train_model()
    print("\n" + "=" * 50)
    print("TRAINING COMPLETE")
    print("=" * 50)
    print(json.dumps(metrics, indent=2))
