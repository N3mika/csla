# SLA_LENS Annotated Corpus Analysis


## Training corpus at a glance

- Total potential training instances: **21,835** sentence rows.
- Instances with at least one classroom-event label: **21,822** (99.94%).
- Distinct observed classroom-event labels: **26**.
- Labels with fewer than 10 examples: **2**.
- Quality-control issues flagged: **25** issue records.
- Repeated-sentence-and-role groups with differing annotations: **408**.

Percentages in the detailed tables use explicitly named denominators. `percent_of_all_sentences`
uses every sentence row; `percent_of_all_label_occurrences` counts each label in a multi-label
row; and `percent_within_family_occurrences` uses only labels from the named family.

## Corpus overview

| metric | value | definition | percent_of_all_sentences |
| --- | --- | --- | --- |
| Transcripts / CSV files | 40.000 | Number of source CSV files |  |
| Total training instances | 21835.000 | One sentence row = one potential training instance |  |
| Instructor sentences | 14648.000 | Rows with instructor role | 67.085 |
| Learner sentences | 7187.000 | Rows with learner role | 32.915 |
| Other/unknown-role sentences | 0.000 | Rows whose role is not instructor or learner | 0.000 |
| Sentences with classroom labels | 21822.000 | Rows usable for classroom-event label training | 99.940 |
| Sentences without classroom labels | 13.000 | Rows with an empty labels field | 0.060 |
| Single-label sentences | 21106.000 | Exactly one classroom-event label | 96.661 |
| Multi-label sentences | 716.000 | More than one classroom-event label | 3.279 |
| Classroom-label occurrences | 22586.000 | Counts every label in multi-label rows |  |
| Sentences with learner errors | 2078.000 | Rows with at least one error label | 9.517 |
| Error-label occurrences | 2090.000 | Counts every error label |  |
| Sentences with conversational repair | 360.000 | Rows with at least one repair-organization label | 1.649 |
| Repair-organization occurrences | 360.000 | Counts every repair-organization label |  |
| Total words (approximate) | 106336.000 | Whitespace/word-boundary estimate |  |
| Mean words per sentence | 4.870 | Approximate mean sentence length |  |
| Median words per sentence | 3.000 | Approximate median sentence length |  |
| Distinct speaker-name strings | 84.000 | Distinct speaker strings across all files |  |
| Unique file-speaker identities | 149.000 | Treats the same speaker string in different transcripts as different identities |  |

## Instructor versus learner balance

| speaker_role | sentence_count | percent_of_all_sentences | classroom_label_occurrences | sentences_with_errors | sentences_with_repair_organization | mean_words_per_sentence |
| --- | --- | --- | --- | --- | --- | --- |
| instructor | 14648 | 67.085 | 15377 | 0 | 265 | 5.365 |
| learner | 7187 | 32.915 | 7209 | 2078 | 95 | 3.861 |

## Classroom-event label distribution

| label | sentence_count | percent_of_all_sentences | percent_of_all_label_occurrences | standalone_count | in_combination_count |
| --- | --- | --- | --- | --- | --- |
| PR | 4172 | 19.107 | 18.472 | 4153 | 19 |
| CoM | 3914 | 17.925 | 17.329 | 3723 | 191 |
| P:I | 2536 | 11.614 | 11.228 | 2424 | 112 |
| P:IQ | 2448 | 11.211 | 10.839 | 2246 | 202 |
| F:Pr | 1616 | 7.401 | 7.155 | 1219 | 397 |
| RN | 1517 | 6.948 | 6.717 | 1469 | 48 |
| CM | 1482 | 6.787 | 6.562 | 1277 | 205 |
| F:Ack | 972 | 4.452 | 4.304 | 813 | 159 |
| F:MF | 739 | 3.384 | 3.272 | 720 | 19 |
| F:EC | 735 | 3.366 | 3.254 | 682 | 53 |
| SP:CQ | 418 | 1.914 | 1.851 | 412 | 6 |
| R:S | 415 | 1.901 | 1.837 | 413 | 2 |
| A | 346 | 1.585 | 1.532 | 342 | 4 |
| F:R | 225 | 1.030 | 0.996 | 192 | 33 |
| R:IR | 195 | 0.893 | 0.863 | 195 | 0 |
| F:EL | 180 | 0.824 | 0.797 | 159 | 21 |
| UNK | 172 | 0.788 | 0.762 | 172 | 0 |
| F:CR | 167 | 0.765 | 0.739 | 164 | 3 |
| R:Ack | 109 | 0.499 | 0.483 | 109 | 0 |
| SP:IQ | 83 | 0.380 | 0.367 | 79 | 4 |
| F:CC | 49 | 0.224 | 0.217 | 49 | 0 |
| P:CQ | 42 | 0.192 | 0.186 | 42 | 0 |
| SP | 29 | 0.133 | 0.128 | 28 | 1 |
| F:NE | 19 | 0.087 | 0.084 | 18 | 1 |
| SP:I | 4 | 0.018 | 0.018 | 4 | 0 |
| R:NR | 2 | 0.009 | 0.009 | 2 | 0 |

## Main label families

| label_family | sentence_count | percent_of_all_sentences | label_occurrences | instructor_sentence_count | learner_sentence_count |
| --- | --- | --- | --- | --- | --- |
| Instructor prompt | 5019 | 22.986 | 5026 | 5019 | 0 |
| Feedback | 4487 | 20.550 | 4702 | 4486 | 1 |
| Prompt response | 4172 | 19.107 | 4172 | 23 | 4149 |
| Conversation management | 3914 | 17.925 | 3914 | 2230 | 1684 |
| Instructor reaction | 1517 | 6.948 | 1517 | 1516 | 1 |
| Classroom management | 1482 | 6.787 | 1482 | 1383 | 99 |
| Repair outcome / uptake | 721 | 3.302 | 721 | 0 | 721 |
| Student prompt | 533 | 2.441 | 534 | 0 | 533 |
| Instructor answer | 346 | 1.585 | 346 | 346 | 0 |
| Unknown | 172 | 0.788 | 172 | 153 | 19 |

## Feedback subtypes

| label | sentence_count | percent_within_family_occurrences | standalone_count | in_combination_count |
| --- | --- | --- | --- | --- |
| F:Pr | 1616 | 34.368 | 1219 | 397 |
| F:Ack | 972 | 20.672 | 813 | 159 |
| F:MF | 739 | 15.717 | 720 | 19 |
| F:EC | 735 | 15.632 | 682 | 53 |
| F:R | 225 | 4.785 | 192 | 33 |
| F:EL | 180 | 3.828 | 159 | 21 |
| F:CR | 167 | 3.552 | 164 | 3 |
| F:CC | 49 | 1.042 | 49 | 0 |
| F:NE | 19 | 0.404 | 18 | 1 |

## Instructor and student prompt subtypes

| family | label | sentence_count | percent_within_family_occurrences |
| --- | --- | --- | --- |
| Instructor prompt | P:I | 2536 | 50.458 |
| Instructor prompt | P:IQ | 2448 | 48.707 |
| Instructor prompt | P:CQ | 42 | 0.836 |
| Student prompt | SP:CQ | 418 | 78.277 |
| Student prompt | SP:IQ | 83 | 15.543 |
| Student prompt | SP | 29 | 5.431 |
| Student prompt | SP:I | 4 | 0.749 |

## Learner repair/uptake outcomes

| label | sentence_count | percent_within_family_occurrences |
| --- | --- | --- |
| R:S | 415 | 57.559 |
| R:IR | 195 | 27.046 |
| R:Ack | 109 | 15.118 |
| R:NR | 2 | 0.277 |

## Learner error labels

| label | sentence_count | percent_within_family_occurrences |
| --- | --- | --- |
| Er:L | 771 | 36.890 |
| Er:G | 631 | 30.191 |
| Er:M | 476 | 22.775 |
| Er:EU | 212 | 10.144 |

## Training-balance indicators

| metric | value | interpretation |
| --- | --- | --- |
| Training instances | 21835.000 | Total sentence rows |
| Labeled training instances | 21822.000 | Rows with at least one classroom label |
| High/medium-confidence instances | 21645.000 | Potential cleaner subset before manual review |
| Instructor-role instances | 14648.000 | Potential instances for instructor-label modeling |
| Learner-role instances | 7187.000 | Potential instances for learner-label and error modeling |
| Feedback-positive instances | 4487.000 | Rows containing a feedback subtype |
| Prompt-positive instances | 5552.000 | Rows containing an instructor or student prompt label |
| Repair-outcome-positive instances | 721.000 | Rows containing learner uptake/repair outcome labels |
| Error-positive learner instances | 2078.000 | Learner rows with at least one error label |
| Conversational-repair-positive instances | 360.000 | Rows containing repair-organization labels |
| Unique observed classroom labels | 26.000 | Number of distinct labels present |
| Mean label cardinality | 1.034 | Mean classroom labels per sentence, including unlabeled rows |
| Multi-label density | 0.040 | Mean label cardinality divided by observed label count |
| Label entropy (bits) | 3.618 | Shannon entropy of classroom-label occurrence distribution |
| Normalized label entropy | 0.770 | Entropy divided by maximum possible entropy; closer to 1 is more balanced |
| Effective number of labels | 12.281 | 2 raised to label entropy |
| Max/min label imbalance ratio | 2086.000 | Most frequent label count divided by least frequent observed label count |
| Labels below 10 instances | 2.000 | Observed labels below configured rare-label threshold |

## Interpretation notes

- `standalone_count` means the label is the only classroom-event label on that sentence.
- `in_combination_count` means the same label occurs with at least one additional label.
- Repair/uptake outcomes (`R:S`, `R:Ack`, `R:IR`, `R:NR`) are reported separately from
  conversational repair organization (`R:SI-SR`, `R:SI-OR`, `R:OI-SR`, `R:OI-OR`).
- Very rare labels may require additional annotation, careful class weighting, label grouping,
  or few-shot evaluation instead of ordinary supervised splitting.
- Review role-label inconsistencies, low/unknown-confidence rows, and same-role annotation variants
  before creating train/dev/test partitions to reduce annotation noise and leakage.
- Fisher tests, when SciPy is installed, are diagnostic associations between speaker role and
  label presence. They do not establish causality and are expected to be strong for role-specific labels.

