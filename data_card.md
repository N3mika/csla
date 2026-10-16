# SLA-LENS Dataset Card

> **Availability:** Restricted research corpus. The classroom transcripts and participant-derived annotations are **not publicly distributed**. This card documents the corpus and its partitions, not a downloadable dataset.

## Overview and intended purpose

SLA-LENS analyzes online second-language (L2) Spanish classroom and language-tutoring interaction. Its corpus contains 40 sentence-segmented, annotated transcripts with instructor/learner roles, conversational context, and classroom-event and learner-error labels. English occurs in instructional discourse and code-switching. The corpus supports research on contextual classroom-event annotation, feedback, learner uptake/repair, and descriptive interactional analytics. It is **not** a benchmark of learner proficiency or teaching effectiveness.

The aggregate figures below are drawn from three supplied CSLA corpus-analysis summaries: the complete 40-transcript corpus, the 35-transcript model-adaptation partition, and the five-transcript held-out silver partition. 

## Corpus size and partitions

| Measure | Full corpus | Model-adaptation partition | Held-out silver partition |
|---|---:|---:|---:|
| Transcripts | 40 | 35 | 5 |
| Sentence rows | 21,835 | 19,214 | 2,621 |
| Instructor rows | 14,648 | 12,920 | 1,728 |
| Learner rows | 7,187 | 6,294 | 893 |
| Rows with classroom-event labels | 21,822 | 19,202 | 2,620 |
| Unlabeled classroom-event rows | 13 | 12 | 1 |
| Single-label rows | 21,106 | 18,583 | 2,523 |
| Multi-label rows | 716 | 619 | 97 |
| Feedback-positive rows | 4,487 | 3,870 | 617 |
| Uptake/repair-positive rows | 721 | 593 | 128 |
| Learner-error-positive rows | 2,078 | 1,828 | 250 |
| Observed classroom-event label types | 26 | 26 | 23 |
| Approximate word count | 106,336 | 92,571 | 13,765 |

The **expert-reviewed gold reference** contains 653 sentence rows from **one of the five held-out transcripts**. The gold reference uses expert-reviewed labels, while the silver reference uses GPT-generated labels, including for the transcript that also has a gold version. Gold and silver scores should be reported separately. 

**Important counting distinction:** Sentence rows are *potential* training instances, not necessarily the number of examples actually passed to fine-tuning. 

## Annotation representation

Transcripts are represented as ordered sentence-level rows with transcript text, sentence identifiers, speaker information, roles, and temporal/turn context. The evaluated SLA-LENS outputs are:

- **`labels`**: ordered classroom-event functions, including instructor prompts (`P:*`), feedback (`F:*`), learner prompt responses (`PR`), uptake/repair outcomes (`R:*`), student prompts (`SP*`), management, reactions, and `UNK`.
- **`error_labels`**: independently assigned learner-language categories: grammatical (`Er:G`), lexical (`Er:L`), multiple errors (`Er:M`), and substantially English production when Spanish is expected (`Er:EU`).

## Distribution and imbalance

The full corpus contains **22,586 classroom-event label occurrences** across 21,835 rows; multi-label rows contribute more than one occurrence. The most frequent individual labels are `PR` (4,172 rows), `CoM` (3,914), `P:I` (2,536), and `P:IQ` (2,448). By contrast, `SP:I` appears four times and `R:NR` twice. These rare categories should not be assumed to support stable subtype-level estimates.

Among the **2,090 learner-error label occurrences** in the full corpus, the reported breakdown is:

| Error category | Occurrences |
|---|---:|
| `Er:L` | 771 |
| `Er:G` | 631 |
| `Er:M` | 476 |
| `Er:EU` | 212 |

The number of error-label occurrences (2,090) exceeds the number of error-positive rows (2,078). Percentages and rates must therefore state whether the denominator is sentence rows, positive rows, or label occurrences.

## Ethical considerations and access

Classroom recordings and transcripts contain participant-derived educational interaction. Even transcripts with pseudonymized speaker labels may disclose identifying information in their content or metadata. **Do not publish original transcript rows, evidence indexes, annotated examples, or generated reports unless explicitly cleared for release.** 

Access to de-identified research materials **can be made available on request**, subject to the responsible institution's authorization, the scope of participant consent, privacy safeguards, and any applicable research-use/data-sharing agreement. Access is discretionary and not guaranteed. The project repository's `DATA_ACCESS.md` should specify the actual contact and request process.
