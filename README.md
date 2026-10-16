# SLA-LENS:Supplementary Repository

This repository provides code, documentation, aggregate corpus statistics, and an example of SLA-LENS, a framework for contextual annotation of L2 classroom interaction and deterministic, evidence-linked descriptive reporting. Author names, affiliations, and contact details are intentionally omitted for review.

SLA-LENS processes classroom transcripts into sentence-level CSLA annotations (prompts, feedback, learner responses, uptake/repair, and independently marked learner-language errors). Its separate Python reporting component turns annotated CSV files into participation and event distributions, learner-level comparisons, lesson timelines, and traceable candidate interaction associations. The reports are **descriptive**: they do not establish proficiency, learning gains, feedback effectiveness, or causal relationships.

## Repository contents

```text
.
├── annotation.py                  # GPT-based contextual annotation
├── evaluation.py                  # Annotation evaluation metrics
├── slalens_report_gen.py          # Deterministic HTML/PDF report generator
├── annotation_guidelines.md       # CSLA labels and decision rules
├── data_card.md                   # Corpus and evaluation partition documentation
├── corpus_statistics.md           # Aggregate statistics for all 40 transcripts
├── DATA_ACCESS.md                 # Restricted-data policy
├── sample_input.txt               # Example transcript (release clearance required)
└── sample_output/
    ├── sample_annotated.csv       # Example annotated transcript
    ├── index.html                 # Example interactive-viewable report
    ├── sample_diagnostic_report.pdf
    ├── charts/                    # Referenced report figures
    ├── error_frequencies.csv
    ├── label_frequencies.csv
    ├── learner_statistics.csv
    ├── speaker_statistics.csv
    ├── sample_evidence_index.csv
    └── sequence_links.csv
```

## Corpus and evaluation design

The corpus contains **40 online L2 Spanish classroom and tutoring transcripts (21,835 sentence rows)**. The designated model-adaptation partition comprises **35 transcripts (19,214 rows)**; the held-out silver partition comprises **five transcripts (2,621 rows)**. An expert-reviewed **653-row gold reference** comes from one of those five held-out transcripts. The gold and silver references overlap at the transcript level, but are scored separately against human-reviewed and GPT-generated labels respectively. The original corpus and participant-derived annotations are **not publicly released**. See [data_card.md](data_card.md), [corpus_statistics.md](corpus_statistics.md), and [DATA_ACCESS.md](DATA_ACCESS.md).

## Requirements

Python 3.10+ is a reasonable starting environment; the exact original environment has not been verified. Install the packages used by the provided scripts:

```bash
python -m pip install openai pandas python-docx tqdm numpy matplotlib
```

## 1. Annotate a transcript

`annotation.py` accepts `.txt`, `.vtt`, and `.docx` transcript files and calls the GPT-4.1 API. Before running it, edit the following constants near the top of the script:

```python
INPUT_DIR = Path("path/to/transcripts")
OUTPUT_DIR = Path("path/to/annotated_outputs")
INTERMEDIATE_DIR = Path("path/to/checkpoints")
```

Set `OPENAI_API_KEY` in your local environment without committing it to the repository. Place input transcripts in `INPUT_DIR`, then run:

```bash
python annotation.py
```

Optional arguments include `--start-from FILENAME` and `--continue-on-error`. The annotation workflow uses **12 target rows**, up to **five preceding rows** and **two following rows**, with role-sensitive CSLA guidelines and resumable checkpoints. API use may incur charges. Do not send restricted participant transcripts to a third-party API without appropriate authorization.

**Scope:** The annotation script also supports an auxiliary `repair_labels` field for conversational repair organization. The paper's evaluated annotation outputs are `labels` and `error_labels`.

## 2. Evaluate annotations

`evaluation.py` compares a reference annotated CSV with a predicted annotated CSV. Set its four configuration constants:

```python
GOLD_FILE = Path("path/to/reference.csv")
PRED_FILE = Path("path/to/predicted.csv")
OUTPUT_DIR = Path("path/to/evaluation_results")
OUTPUT_PREFIX = "example"
```

Then run:

```bash
python evaluation.py
```

## 3. Generate the analytical report

`slalens_report_gen.py` reads an annotated CSV and produces a deterministic report. Set these constants in the script:

```python
INPUT_CSV = Path("sample_output/sample_annotated.csv")
OUTPUT_DIR = Path("path/to/generated_report")
```

Run:

```bash
python slalens_report_gen.py
```

Open the generated `index.html` in a local browser, keeping its `charts/` directory alongside it. The existing `sample_output/index.html` and `sample_diagnostic_report.pdf` are illustrative snapshots; the current script may regenerate different files if the input or settings differ. The report links errors to corrective feedback, feedback to uptake, and prompts to responses using a **maximum of four intervening transcript rows**, stopping at another source event. These are proximity-based *candidates*, not verified interactional episodes.

## Interpretation and limitations

- Counts generally represent annotated **sentence rows**, not time spent speaking; repeated timestamps can make speaking-time estimates unreliable.
- Learner error incidence is normalized per learner row where applicable and is **not** a proficiency score.
- Rare label subtypes, ASR noise, and context-dependent annotation decisions limit interpretation.
- The reporting layer computes summaries from supplied annotations; it does **not** use another LLM to invent narrative conclusions.
- The public sample does not substitute for the restricted gold/silver datasets or reproduce the paper's experimental scores without the corresponding reference and prediction files.
