from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

GOLD_FILE = Path(r"---")
PRED_FILE = Path(r"---")
OUTPUT_DIR = Path(r"---")
OUTPUT_PREFIX = "---"

FEEDBACK = {
    "F:EC", "F:R", "F:CR", "F:EL", "F:MF", "F:CC", "F:Pr", "F:Ack", "F:NE"
}
UPTAKE = {"R:S", "R:Ack", "R:IR", "R:NR"}
PROMPT = {"P:I", "P:IQ", "P:CQ"}
STUDENT_PROMPT = {"SP", "SP:I", "SP:IQ", "SP:CQ"}
ERRORS = {"Er:G", "Er:L", "Er:M", "Er:EU"}

OTHER_MAIN = {"A", "RN", "CoM", "CM", "PR", "UNK"}
VALID_MAIN = FEEDBACK | UPTAKE | PROMPT | STUDENT_PROMPT | OTHER_MAIN
VALID_ERROR = ERRORS

INSTRUCTOR_ONLY = FEEDBACK | PROMPT | {"A", "RN"}
LEARNER_ONLY = UPTAKE | STUDENT_PROMPT | {"PR"}
ROLE_NEUTRAL = {"CM", "CoM", "UNK"}

# Soft-score constants.
EXACT_CREDIT = 1.00
SAME_FAMILY_CREDIT = 0.70
SAME_ROLE_CREDIT = 0.25
CROSS_ROLE_CREDIT = 0.00
ORDER_PENALTY = 0.85  # applied when >=2 exact common labels occur in a different order

CANONICAL_CASE = {x.lower(): x for x in VALID_MAIN | VALID_ERROR}


@dataclass
class DetectionMetrics:
    support_positive: int
    predicted_positive: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


@dataclass
class EvaluationSummary:
    n_rows: int
    hard_accuracy: float
    soft_score: float
    feedback: DetectionMetrics
    uptake_repair: DetectionMetrics
    error_detection: DetectionMetrics
    error_hard_accuracy: float
    main_invalid_gold: int
    main_invalid_pred: int
    error_invalid_gold: int
    error_invalid_pred: int
    role_violations_gold: int
    role_violations_pred: int


def _norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


COLUMN_ALIASES = {
    "id": {"sentenceid", "sentence_id", "id", "utteranceid", "rowid"},
    "role": {"speakerrole", "speaker_role", "role"},
    "labels": {"labels", "label", "classroomeventlabels", "eventlabels"},
    "errors": {"errorlabels", "error_labels", "errors", "errorlabel"},
    "sentence": {"sentence", "sentenceoriginal", "sentence_original", "text", "utterance"},
    "speaker": {"speaker", "speakername", "speaker_name"},
}
COLUMN_ALIASES = {k: {_norm_col(x) for x in v} for k, v in COLUMN_ALIASES.items()}


def detect_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:10000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return "\t" if "\t" in sample else ","


def read_table(path: Path) -> Tuple[List[Dict[str, str]], Dict[str, Optional[str]]]:
    delim = detect_delimiter(path)
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delim)
        if not reader.fieldnames:
            raise ValueError(f"No header found in {path}")
        fields = list(reader.fieldnames)
        norm_to_orig = {_norm_col(x): x for x in fields}
        mapping: Dict[str, Optional[str]] = {}
        for key, aliases in COLUMN_ALIASES.items():
            mapping[key] = next((norm_to_orig[a] for a in aliases if a in norm_to_orig), None)
        if mapping["labels"] is None:
            raise ValueError(f"Could not find a Labels column in {path}. Headers: {fields}")
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]
    return rows, mapping


def canonical_label(raw: str) -> str:
    x = raw.strip().strip("[](){}\"'").strip()
    x = re.sub(r"\s+", "", x)
    return CANONICAL_CASE.get(x.lower(), x)


def parse_labels(value: object) -> List[str]:
    if value is None:
        return []
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "na", "n/a", "-", "—"}:
        return []
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s.replace("'", '"'))
            if isinstance(arr, list):
                return [canonical_label(str(x)) for x in arr if str(x).strip()]
        except Exception:
            pass
    parts = re.split(r"\s*[,;|]\s*", s)
    return [canonical_label(p) for p in parts if canonical_label(p)]


def normalize_role(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s in {"teacher", "instructor", "professor", "t", "i"}:
        return "instructor"
    if s in {"student", "learner", "s", "l"}:
        return "learner"
    return "unknown"


def label_family(label: str) -> str:
    if label in FEEDBACK:
        return "feedback"
    if label in UPTAKE:
        return "uptake_repair"
    if label in PROMPT:
        return "instructor_prompt"
    if label in STUDENT_PROMPT:
        return "student_prompt"
    if label == "PR":
        return "prompt_response"
    if label == "A":
        return "instructor_answer"
    if label == "RN":
        return "instructor_reaction"
    if label == "CM":
        return "classroom_management"
    if label == "CoM":
        return "conversation_management"
    if label == "UNK":
        return "unknown"
    return "invalid"


def allowed_roles(label: str) -> set[str]:
    if label in INSTRUCTOR_ONLY:
        return {"instructor"}
    if label in LEARNER_ONLY:
        return {"learner"}
    if label in ROLE_NEUTRAL:
        return {"instructor", "learner"}
    return set()


def role_compatible(label: str, row_role: str) -> bool:
    if row_role == "unknown":
        return True  
    return row_role in allowed_roles(label)


def pair_credit(gold: str, pred: str, row_role: str) -> float:
    """Semantic credit for pairing one predicted label to one gold label."""
    if gold == pred:
        return EXACT_CREDIT
    gf, pf = label_family(gold), label_family(pred)
    if gf != "invalid" and gf == pf:
        return SAME_FAMILY_CREDIT
    if role_compatible(gold, row_role) and role_compatible(pred, row_role):
        return SAME_ROLE_CREDIT
    return CROSS_ROLE_CREDIT


def best_alignment_credit(gold: Sequence[str], pred: Sequence[str], role: str) -> float:
    if not gold and not pred:
        return 1.0
    if not gold or not pred:
        return 0.0

    m = len(pred)
    dp: Dict[int, float] = {0: 0.0}
    for g in gold:
        new = dict(dp)  # option to leave this gold label unmatched
        for mask, val in dp.items():
            for j, p in enumerate(pred):
                if not (mask >> j) & 1:
                    nm = mask | (1 << j)
                    nv = val + pair_credit(g, p, role)
                    if nv > new.get(nm, -1.0):
                        new[nm] = nv
        dp = new
    best = max(dp.values())
    return best / max(len(gold), len(pred))


def exact_common_order_changed(gold: Sequence[str], pred: Sequence[str]) -> bool:
    common = set(gold) & set(pred)
    if len(common) < 2:
        return False
    gseq = [x for x in gold if x in common]
    pseq = [x for x in pred if x in common]
    return gseq != pseq


def row_soft_score(gold: Sequence[str], pred: Sequence[str], role: str) -> float:
    base = best_alignment_credit(gold, pred, role)
    if exact_common_order_changed(gold, pred):
        base *= ORDER_PENALTY
    return 100.0 * base


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def binary_detection(gold_rows: Sequence[Sequence[str]], pred_rows: Sequence[Sequence[str]], family: set[str]) -> DetectionMetrics:
    tp = fp = fn = 0
    support = predicted = 0
    for g, p in zip(gold_rows, pred_rows):
        gy = any(x in family for x in g)
        py = any(x in family for x in p)
        support += int(gy)
        predicted += int(py)
        tp += int(gy and py)
        fp += int((not gy) and py)
        fn += int(gy and (not py))
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return DetectionMetrics(support, predicted, tp, fp, fn, precision, recall, f1)


def row_key(row: Dict[str, str], mapping: Dict[str, Optional[str]], idx: int) -> str:
    c = mapping.get("id")
    if c and str(row.get(c, "")).strip():
        return str(row[c]).strip()
    return f"__row_{idx}"


def align_rows(
    gold: List[Dict[str, str]], gm: Dict[str, Optional[str]],
    pred: List[Dict[str, str]], pm: Dict[str, Optional[str]],
) -> List[Tuple[Dict[str, str], Dict[str, str]]]:
    if gm.get("id") and pm.get("id"):
        pmap = {row_key(r, pm, i): r for i, r in enumerate(pred)}
        pairs = []
        missing = []
        for i, g in enumerate(gold):
            k = row_key(g, gm, i)
            if k not in pmap:
                missing.append(k)
            else:
                pairs.append((g, pmap[k]))
        if missing:
            raise ValueError(f"Prediction file is missing {len(missing)} gold sentence_id(s), e.g. {missing[:5]}")
        if len(pmap) != len(pred):
            raise ValueError("Duplicate sentence_id values found in prediction file.")
        return pairs
    if len(gold) != len(pred):
        raise ValueError(f"No shared sentence_id column and row counts differ: gold={len(gold)}, pred={len(pred)}")
    return list(zip(gold, pred))


def invalid_count(rows: Sequence[Sequence[str]], valid: set[str]) -> int:
    return sum(1 for labels in rows for x in labels if x not in valid)


def role_violation_count(rows: Sequence[Sequence[str]], roles: Sequence[str]) -> int:
    return sum(1 for labels, role in zip(rows, roles) for x in labels if x in VALID_MAIN and not role_compatible(x, role))


def label_families(labels: Sequence[str]) -> List[str]:
    return [label_family(x) for x in labels]


def diagnostic_flags(gold: Sequence[str], pred: Sequence[str], family: set[str]) -> Dict[str, bool]:
    gy = any(x in family for x in gold)
    py = any(x in family for x in pred)
    return {
        "gold": gy,
        "pred": py,
        "tp": gy and py,
        "fp": (not gy) and py,
        "fn": gy and (not py),
        "tn": (not gy) and (not py),
    }


def invalid_labels(labels: Sequence[str], valid: set[str]) -> List[str]:
    return [x for x in labels if x not in valid]


def evaluate(gold_path: Path, pred_path: Path) -> Tuple[EvaluationSummary, List[Dict[str, object]]]:
    gold, gm = read_table(gold_path)
    pred, pm = read_table(pred_path)
    pairs = align_rows(gold, gm, pred, pm)

    g_main: List[List[str]] = []
    p_main: List[List[str]] = []
    g_err: List[List[str]] = []
    p_err: List[List[str]] = []
    roles: List[str] = []
    details: List[Dict[str, object]] = []

    hard_hits = 0
    err_hard_hits = 0
    soft_total = 0.0

    for idx, (g, p) in enumerate(pairs):
        gl = parse_labels(g.get(gm["labels"], ""))
        pl = parse_labels(p.get(pm["labels"], ""))
        ge = parse_labels(g.get(gm["errors"], "")) if gm.get("errors") else []
        pe = parse_labels(p.get(pm["errors"], "")) if pm.get("errors") else []

        role_raw = g.get(gm["role"], "") if gm.get("role") else ""
        if not str(role_raw).strip() and pm.get("role"):
            role_raw = p.get(pm["role"], "")
        role = normalize_role(role_raw)

        hard = gl == pl
        e_hard = ge == pe
        soft = row_soft_score(gl, pl, role)
        hard_hits += int(hard)
        err_hard_hits += int(e_hard)
        soft_total += soft

        g_main.append(gl); p_main.append(pl); g_err.append(ge); p_err.append(pe); roles.append(role)
        fb = diagnostic_flags(gl, pl, FEEDBACK)
        up = diagnostic_flags(gl, pl, UPTAKE)
        er = diagnostic_flags(ge, pe, ERRORS)

        sentence_col = gm.get("sentence")
        speaker_col = gm.get("speaker")
        sentence_text = g.get(sentence_col, "") if sentence_col else ""
        speaker_name = g.get(speaker_col, "") if speaker_col else ""

        details.append({
            "row": idx + 1,
            "sentence_id": row_key(g, gm, idx),
            "speaker_role": role,
            "speaker": speaker_name,
            "sentence": sentence_text,
            "gold_labels": gl,
            "pred_labels": pl,
            "gold_label_families": label_families(gl),
            "pred_label_families": label_families(pl),
            "hard_match": hard,
            "soft_score": round(soft, 4),
            "gold_feedback": fb["gold"],
            "pred_feedback": fb["pred"],
            "feedback_tp": fb["tp"],
            "feedback_fp": fb["fp"],
            "feedback_fn": fb["fn"],
            "feedback_tn": fb["tn"],
            "gold_uptake_repair": up["gold"],
            "pred_uptake_repair": up["pred"],
            "uptake_repair_tp": up["tp"],
            "uptake_repair_fp": up["fp"],
            "uptake_repair_fn": up["fn"],
            "uptake_repair_tn": up["tn"],
            "gold_error_labels": ge,
            "pred_error_labels": pe,
            "gold_error_present": er["gold"],
            "pred_error_present": er["pred"],
            "error_tp": er["tp"],
            "error_fp": er["fp"],
            "error_fn": er["fn"],
            "error_tn": er["tn"],
            "error_detection_match": er["gold"] == er["pred"],
            "error_hard_match": e_hard,
            "gold_invalid_main_labels": invalid_labels(gl, VALID_MAIN),
            "pred_invalid_main_labels": invalid_labels(pl, VALID_MAIN),
            "gold_invalid_error_labels": invalid_labels(ge, VALID_ERROR),
            "pred_invalid_error_labels": invalid_labels(pe, VALID_ERROR),
            "gold_role_violation": any(x in VALID_MAIN and not role_compatible(x, role) for x in gl),
            "pred_role_violation": any(x in VALID_MAIN and not role_compatible(x, role) for x in pl),
        })

    n = len(pairs)
    if n == 0:
        raise ValueError("No aligned rows to evaluate.")

    summary = EvaluationSummary(
        n_rows=n,
        hard_accuracy=hard_hits / n,
        soft_score=soft_total / n,
        feedback=binary_detection(g_main, p_main, FEEDBACK),
        uptake_repair=binary_detection(g_main, p_main, UPTAKE),
        error_detection=binary_detection(g_err, p_err, ERRORS),
        error_hard_accuracy=err_hard_hits / n,
        main_invalid_gold=invalid_count(g_main, VALID_MAIN),
        main_invalid_pred=invalid_count(p_main, VALID_MAIN),
        error_invalid_gold=invalid_count(g_err, VALID_ERROR),
        error_invalid_pred=invalid_count(p_err, VALID_ERROR),
        role_violations_gold=role_violation_count(g_main, roles),
        role_violations_pred=role_violation_count(p_main, roles),
    )
    return summary, details


def pct(x: float) -> str:
    return f"{100*x:.2f}%"


def print_summary(s: EvaluationSummary) -> None:
    print("\nCSLA EVALUATION")
    print("=" * 72)
    print(f"Rows evaluated              : {s.n_rows}")
    print(f"Hard Accuracy               : {pct(s.hard_accuracy)}")
    print(f"Soft Score                  : {s.soft_score:.2f} / 100")
    print(f"Feedback detection F1       : {s.feedback.f1:.4f}  (P={s.feedback.precision:.4f}, R={s.feedback.recall:.4f}, n={s.feedback.support_positive})")
    print(f"Uptake/Repair detection F1  : {s.uptake_repair.f1:.4f}  (P={s.uptake_repair.precision:.4f}, R={s.uptake_repair.recall:.4f}, n={s.uptake_repair.support_positive})")
    print(f"Error detection F1          : {s.error_detection.f1:.4f}  (P={s.error_detection.precision:.4f}, R={s.error_detection.recall:.4f}, n={s.error_detection.support_positive})")
    print(f"Error Hard Accuracy         : {pct(s.error_hard_accuracy)}")
    print("-" * 72)
    print(f"Invalid main labels (G/P)   : {s.main_invalid_gold} / {s.main_invalid_pred}")
    print(f"Invalid error labels (G/P)  : {s.error_invalid_gold} / {s.error_invalid_pred}")
    print(f"Role violations (G/P)       : {s.role_violations_gold} / {s.role_violations_pred}")


def save_details_csv(details: List[Dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        fields = list(details[0].keys()) if details else []
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        list_fields = {
            "gold_labels", "pred_labels", "gold_label_families", "pred_label_families",
            "gold_error_labels", "pred_error_labels",
            "gold_invalid_main_labels", "pred_invalid_main_labels",
            "gold_invalid_error_labels", "pred_invalid_error_labels",
        }
        for row in details:
            out = dict(row)
            for k in list_fields:
                if k in out and isinstance(out[k], list):
                    out[k] = ",".join(out[k])
            w.writerow(out)


def main() -> None:
    gold_path = GOLD_FILE.expanduser()
    pred_path = PRED_FILE.expanduser()
    out_dir = OUTPUT_DIR.expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not gold_path.exists():
        raise FileNotFoundError(f"Gold file not found: {gold_path}. Edit GOLD_FILE at the top of the script.")
    if not pred_path.exists():
        raise FileNotFoundError(f"Prediction file not found: {pred_path}. Edit PRED_FILE at the top of the script.")

    summary, details = evaluate(gold_path, pred_path)
    print_summary(summary)

    summary_path = out_dir / f"{OUTPUT_PREFIX}_summary.json"
    details_path = out_dir / f"{OUTPUT_PREFIX}_row_evaluation.csv"

    summary_path.write_text(json.dumps(asdict(summary), indent=2, ensure_ascii=False), encoding="utf-8")
    save_details_csv(details, details_path)

    print(f"\nSaved JSON summary       : {summary_path}")
    print(f"Saved row-level evaluation: {details_path}")


if __name__ == "__main__":
    main()
