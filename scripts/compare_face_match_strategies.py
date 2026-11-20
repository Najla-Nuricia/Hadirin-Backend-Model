"""Fair comparison of average-centroid vs multiple-reference face matching.

Protocol
--------
1. A single CSV manifest defines identity / split / image for both methods.
2. Splits: `enroll` (references), `calib` (threshold tuning), `test` (final FAR/FRR).
3. The same MTCNN + MobileFaceNet engine and preprocessing extract every embedding once.
4. For each probe, score against every enrolled identity:
      average  -> cosine(probe, L2-normalized centroid of that identity's references)
      multiple -> max cosine(probe, each reference)
5. Threshold is calibrated per method on `calib` only, by minimizing |FAR - FRR|
   (EER-style), then evaluated once on `test`.

No metrics are invented: without enroll/calib/test rows for >= 2 identities the
script exits with an error. `--smoke` only verifies the pipeline on the tiny
fixture set and prints a loud warning that its numbers are NOT a valid evaluation.

Manifest example (paths relative to --dataset-root):
    identity,split,path
    mahasiswa_001,enroll,id001/a.jpg
    mahasiswa_001,enroll,id001/b.jpg
    mahasiswa_001,calib,id001/c.jpg
    mahasiswa_001,test,id001/d.jpg
    mahasiswa_002,enroll,id002/a.jpg
    ...
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from ml.inference.face_embedder import (
    FaceMatchStrategy,
    get_face_engine,
)

FIXTURES = Path(__file__).resolve().parents[1] / "qa" / "fixtures" / "faces"
STRATEGIES: tuple[FaceMatchStrategy, ...] = ("average", "multiple")
SPLITS = ("enroll", "calib", "test")


def load_manifest(path: Path, root: Path) -> list[dict[str, str]]:
    """Read and validate the common manifest used by both methods."""
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"identity", "split", "path"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Manifest harus punya kolom {sorted(required)}")
        for line_no, row in enumerate(reader, start=2):
            identity = (row.get("identity") or "").strip()
            split = (row.get("split") or "").strip().lower()
            raw_path = (row.get("path") or "").strip()
            if not identity or split not in SPLITS or not raw_path:
                raise ValueError(f"Baris {line_no} manifest tidak valid: {row}")
            image = Path(raw_path)
            if not image.is_absolute():
                image = root / image
            if not image.is_file():
                raise ValueError(f"Baris {line_no}: file tidak ditemukan: {image}")
            rows.append({"identity": identity, "split": split, "path": str(image)})

    identities = {r["identity"] for r in rows}
    if len(identities) < 2:
        raise ValueError("Minimal 2 identitas diperlukan untuk FAR/FRR.")
    for split in SPLITS:
        if not {r["identity"] for r in rows if r["split"] == split}:
            raise ValueError(f"Split '{split}' tidak memiliki data.")
    for identity in identities:
        own = {r["split"] for r in rows if r["identity"] == identity}
        if "enroll" not in own or not ({"calib", "test"} & own):
            raise ValueError(
                f"Identitas '{identity}' butuh enroll + (calib atau test); ditemukan {sorted(own)}"
            )
    return rows


def smoke_rows() -> list[dict[str, str]]:
    """Tiny fixture manifest for pipeline verification only (leaky, not publishable)."""
    names = {
        "sheldon_ref.jpg": ("sheldon", "enroll"),
        "sheldon_probe.jpg": ("sheldon", "calib"),
        "leonard_probe.jpg": ("leonard", "enroll"),
    }
    rows = [
        {"identity": identity, "split": split, "path": str(FIXTURES / name)}
        for name, (identity, split) in names.items()
    ]
    rows += [
        {"identity": "sheldon", "split": "test", "path": str(FIXTURES / "sheldon_probe.jpg")},
        {"identity": "leonard", "split": "test", "path": str(FIXTURES / "leonard_probe.jpg")},
        {"identity": "leonard", "split": "calib", "path": str(FIXTURES / "leonard_probe.jpg")},
    ]
    return rows


def extract_all(rows: list[dict[str, str]], engine: Any) -> dict[str, list[float]]:
    """Extract each unique image once so both methods share identical embeddings."""
    cache: dict[str, list[float]] = {}
    for row in rows:
        if row["path"] not in cache:
            cache[row["path"]] = engine.extract_embedding_from_bytes(Path(row["path"]).read_bytes())
    return cache


def score_split(
    rows: list[dict[str, str]],
    split: str,
    embeddings: dict[str, list[float]],
    strategy: FaceMatchStrategy,
) -> tuple[list[float], list[float]]:
    """Return (genuine_scores, impostor_scores) for one split and one method."""
    enrollments: dict[str, list[list[float]]] = {}
    for row in rows:
        if row["split"] == "enroll":
            enrollments.setdefault(row["identity"], []).append(embeddings[row["path"]])

    genuine: list[float] = []
    impostor: list[float] = []
    from ml.inference.face_embedder import FaceRecognitionEngine

    for row in rows:
        if row["split"] != split:
            continue
        probe = embeddings[row["path"]]
        for identity, references in enrollments.items():
            score = FaceRecognitionEngine.compare_embeddings(probe, references, strategy)
            (genuine if identity == row["identity"] else impostor).append(score)
    return genuine, impostor


def calibration(genuine: list[float], impostor: list[float]) -> float:
    """Pick threshold minimizing |FAR-FRR| on calibration data (EER-style)."""
    if not genuine or not impostor:
        raise ValueError("Kalibrasi butuh skor genuine dan impostor.")
    scores = sorted(set(genuine + impostor))

    def rates(threshold: float) -> tuple[float, float]:
        far = sum(s >= threshold for s in impostor) / len(impostor)
        frr = sum(s < threshold for s in genuine) / len(genuine)
        return far, frr

    return min(scores, key=lambda t: (abs(rates(t)[0] - rates(t)[1]), sum(rates(t)), -t))


def evaluate(genuine: list[float], impostor: list[float], threshold: float) -> dict[str, Any]:
    """Compute FAR/FRR and confusion matrix at a fixed threshold."""
    if not genuine or not impostor:
        raise ValueError("Evaluasi butuh skor genuine dan impostor.")
    tp = sum(s >= threshold for s in genuine)
    fn = len(genuine) - tp
    fp = sum(s >= threshold for s in impostor)
    tn = len(impostor) - fp
    return {
        "threshold": round(threshold, 6),
        "far": round(fp / len(impostor), 6),
        "frr": round(fn / len(genuine), 6),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "genuine_pairs": len(genuine),
        "impostor_pairs": len(impostor),
        "accuracy": round((tp + tn) / (len(genuine) + len(impostor)), 6),
    }


def render_markdown(results: dict[str, dict[str, Any]], smoke: bool) -> str:
    """Render a factual comparison table, confusion matrices, and analysis."""
    header = "# Perbandingan Average vs Multiple Embedding"
    if smoke:
        header += "\n\n> ⚠️ SMOKE TEST — angka di bawah **tidak valid** untuk FAR/FRR."

    lines = [
        header,
        "",
        "| Metode | Threshold (calib) | FAR (test) | FRR (test) | TP | FN | FP | TN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy in STRATEGIES:
        m = results[strategy]["test"]
        lines.append(
            f"| {strategy} | {m['threshold']:.4f} | {m['far']:.4f} | {m['frr']:.4f} "
            f"| {m['tp']} | {m['fn']} | {m['fp']} | {m['tn']} |"
        )

    for strategy in STRATEGIES:
        m = results[strategy]["test"]
        lines += [
            "",
            f"### Confusion matrix — {strategy}",
            "",
            "| Aktual \\ Prediksi | Diterima | Ditolak |",
            "|---|---:|---:|",
            f"| Genuine | {m['tp']} | {m['fn']} |",
            f"| Impostor | {m['fp']} | {m['tn']} |",
        ]

    # Data-driven conclusion: lower total error on test wins; exact tie is reported as a tie.
    totals = {
        s: results[s]["test"]["far"] + results[s]["test"]["frr"] for s in STRATEGIES
    }
    if totals["average"] == totals["multiple"]:
        conclusion = "kedua metode memiliki total error (FAR+FRR) yang sama pada data ini"
    else:
        winner = min(STRATEGIES, key=lambda s: totals[s])
        conclusion = f"total error (FAR+FRR) terendah dicapai oleh **{winner}**"

    lines += [
        "",
        "## Analisis",
        "",
        "- Threshold dikalibrasi terpisah pada split `calib` (EER-style), lalu diuji sekali pada `test`.",
        f"- Berdasarkan tabel di atas, {conclusion}.",
        "- Jika jumlah pasangan impostor/genuine kecil, selisih satu keputusan dapat mengubah FAR/FRR "
        "secara besar — gunakan dataset dengan banyak identitas dan beberapa sampel per identitas.",
    ]
    if smoke:
        lines += [
            "",
            "- Fixture hanya punya satu foto referensi per identitas, sehingga `multiple` identik dengan `average`.",
            "**Jangan gunakan angka ini untuk menentukan strategi produksi.**",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="CSV: identity,split,path")
    parser.add_argument("--dataset-root", type=Path, default=Path("."), help="Root untuk path relatif")
    parser.add_argument("--out-dir", type=Path, default=Path("qa/reports"))
    parser.add_argument("--smoke", action="store_true", help="Jalankan pipeline pada fixture kecil (bukan evaluasi)")
    args = parser.parse_args()

    if args.smoke:
        rows = smoke_rows()
    elif args.manifest:
        rows = load_manifest(args.manifest, args.dataset_root)
    else:
        parser.error("--manifest wajib diisi kecuali --smoke digunakan")

    settings = get_settings()
    engine = get_face_engine(
        weights_dir=str(settings.ml_weights_dir),
        min_face_size=settings.mtcnn_min_face_size,
    )
    embeddings = extract_all(rows, engine)

    results: dict[str, dict[str, Any]] = {}
    for strategy in STRATEGIES:
        calib_genuine, calib_impostor = score_split(rows, "calib", embeddings, strategy)
        threshold = calibration(calib_genuine, calib_impostor)
        test_genuine, test_impostor = score_split(rows, "test", embeddings, strategy)
        results[strategy] = {
            "calib": evaluate(calib_genuine, calib_impostor, threshold),
            "test": evaluate(test_genuine, test_impostor, threshold),
        }

    markdown = render_markdown(results, smoke=args.smoke)
    print(markdown)
    if args.smoke:
        print("MODE SMOKE: tidak ada laporan yang ditulis. FAR/FRR di atas bukan hasil eksperimen.")
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "face_match_comparison.json").write_text(
        json.dumps({"strategies": list(STRATEGIES), "results": results}, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "face_match_comparison.md").write_text(markdown, encoding="utf-8")
    print(f"Laporan ditulis ke {args.out_dir / 'face_match_comparison.md'}")


if __name__ == "__main__":
    main()
