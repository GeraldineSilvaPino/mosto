"""Offline baseline CLI. Outputs are explicit and never overwrite existing files."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from .legacy_generator import generate_windows, NOTEBOOK_SHA256

FEATURES = ["brix_suavizado", "temp_suavizada", "pendiente_brix_ventana",
            "pendiente_temp_ventana", "turbulencia_brix_std"]


def dataset(path):
    data = pd.read_csv(path)
    if list(data.columns) != FEATURES + ["riesgo_parada"]:
        raise ValueError("Unexpected feature schema")
    if not np.isfinite(data.to_numpy(dtype=float)).all() or set(data.riesgo_parada) != {0, 1}:
        raise ValueError("Expected finite features and both binary classes")
    return data


def split_indices(data):
    return train_test_split(np.arange(len(data)), test_size=.2, random_state=42, stratify=data.riesgo_parada)


def evaluate(model, data, indices):
    x, y = data.iloc[indices][FEATURES], data.iloc[indices].riesgo_parada
    return {"accuracy": accuracy_score(y, model.predict(x)),
            "roc_auc": roc_auc_score(y, model.predict_proba(x)[:, 1]),
            "confusion_matrix": confusion_matrix(y, model.predict(x)).tolist(),
            "samples": len(indices)}


def provenance(path):
    return {"status": "experimental_synthetic_baseline_not_validated_for_real_wine",
            "dataset_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "source_notebook_sha256": NOTEBOOK_SHA256, "features": FEATURES,
            "physical_step_hours": .25, "points_per_window": 12,
            "target": "preset_synthetic_regime_not_future_stuck_event",
            "split": {"test_fraction": .2, "seed": 42, "stratified": True},
            "python": platform.python_version(),
            "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "joblib")}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--seed", type=int, default=42)
    train = sub.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest_path = args.output.with_suffix(".manifest.json")
        if manifest_path.exists():
            raise FileExistsError(manifest_path)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="") as handle:
            generate_windows(seed=args.seed).to_csv(handle, index=False, lineterminator="\n")
        metadata = provenance(args.output)
        metadata["generation_seed"] = args.seed
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
        return
    # A new directory prevents accidentally replacing the model served by FastAPI.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    data = dataset(args.dataset)
    train_ids, test_ids = split_indices(data)
    model = GradientBoostingClassifier(n_estimators=100, learning_rate=.08, max_depth=4, subsample=.85, random_state=42)
    model.fit(data.iloc[train_ids][FEATURES], data.iloc[train_ids].riesgo_parada)
    report = provenance(args.dataset)
    report.update({"metrics_test": evaluate(model, data, test_ids),
                   "train_indices": train_ids.tolist(), "test_indices": test_ids.tolist(),
                   "model_parameters": model.get_params()})
    artifact = args.output_dir / "model.joblib"
    joblib.dump(model, artifact)
    report["model_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (args.output_dir / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics_test"], indent=2))


if __name__ == "__main__":
    main()
