# SLA-LENS: CSLA Annotation Guidelines

This document summarizes the operational annotation rules used for SLA-LENS. 

## Annotation outputs and scope

Two independently evaluated annotation fields are used:

- **`labels`**: ordered classroom-event labels describing the utterance's communicative function.
- **`error_labels`** (also referred to as `error_labels` / `error\_labels` in documentation): learner-language errors observable in the transcript; empty when none is warranted.

Labels are assigned to sentence-level transcript rows, using preceding and following turns as context. Annotation describes **observable discourse behavior**, not learner proficiency, teaching quality, or verified causal relationships.
## General decision rules

1. Label **communicative function in context**, not grammatical form or isolated keywords.
2. Prefer **one classroom-event label** per row. Assign multiple ordered labels only when independently observable events occur within the same row; do not add labels merely for alternative interpretations.
3. **Instructor feedback takes precedence** over other instructor functions when responding to, evaluating, or facilitating correction of learner production: **F > other instructor functions**.
4. **Learner response/repair takes precedence** within a feedback sequence: **R > other learner functions**. A learner's answer to an ordinary instructional prompt is `PR`, not `R`.
5. **Continuations inherit the function** of the event they elaborate; explanatory detail is not a separate event label.
6. Use **`UNK`** when the instructional/communicative function cannot be determined reliably from the available transcript.
7. Observe **speaker-role restrictions**: instructor prompts and feedback are instructor functions; learner prompt responses, student prompts, and uptake/repair are learner functions. `CM`, `CoM`, and `UNK` can apply to either role.

**Context examples**

| Context | Label | Reason |
|---|---|---|
| Instructor: *Describe el personaje.* | `P:I` | Initiates learner production. |
| After an error, instructor: *Di “tiene”.* | `F:EC` | Supplies a correction rather than assigning a new task. |
| Learner: *Tiene.* after corrective feedback | `R:S` | Repairs the feedback-targeted problem. |
| Learner: *La pizza.* after *¿Cuál es tu comida favorita?* | `PR` | Responds to an instructional prompt. |
| Instructor: *Provide at least two Spanish names.*; then *By Spanish names I mean names such as Juan or María.* | `P:I` on both rows | Second row elaborates the instruction. |
| Instructor: *Muy bien, ahora inténtalo otra vez.* | `F:Pr, F:EL` | Praise followed by elicitation, if both functions are observable. |

## Instructor classroom-event labels

### Prompts (`P:*`)

Prompts elicit learner production or initiate a learning task, rather than responding to a learner error.

| Label | Full name | Operational definition |
|---|---|---|
| `P:I` | Instruction | Assigns a task or directs learner production. |
| `P:IQ` | Information question | Requests new information from the learner. |
| `P:CQ` | Clarification question | Requests clarification outside a corrective-feedback episode. |

### Feedback (`F:*`)

Feedback responds to learner production or the learner's learning process. When feedback is assigned, use a **specific subtype**.

| Label | Full name | Operational definition |
|---|---|---|
| `F:EC` | Explicit correction | Overtly supplies the corrected target form. |
| `F:R` | Recast | Reformulates learner production without explicitly identifying the error. |
| `F:CR` | Clarification request | Requests clarification/repetition following problematic learner production. |
| `F:EL` | Elicitation | Prompts the learner to supply or complete a corrected form. |
| `F:MF` | Metalinguistic feedback | Provides information about the linguistic problem. |
| `F:CC` | Confirmation check | Checks a proposed interpretation or corrected form. |
| `F:Pr` | Praise | Positively evaluates learner language or performance (including class performance). |
| `F:Ack` | Acknowledgement | Acknowledges or repeats a correct learner form without explicit praise. |
| `F:NE` | Negative evaluation | Evaluates learner production as incorrect without supplying a correction. |

**Feedback versus prompt:** An imperative such as *di* or *repite* is `P:I` when starting a task, but feedback when it responds to a learner error. **Praise versus reaction:** `F:Pr` evaluates learner performance; `RN` responds to meaning or emotion without evaluating linguistic accuracy.

### Other instructor functions

| Label | Full name | Operational definition |
|---|---|---|
| `A` | Answer | Answers a learner question without functioning as corrective feedback. |
| `RN` | Reaction | Reacts to the content or emotional aspect of learner speech without evaluating linguistic accuracy. |
| `CM` | Classroom management | Manages technology, participation, lesson logistics, or organization rather than learner-language production. |
| `CoM` | Conversation management | Minimal discourse markers or backchannels regulating conversational flow (e.g., *mhm*, *okay*, *vale*). |

## Learner classroom-event labels

| Label | Full name | Operational definition |
|---|---|---|
| `PR` | Prompt response | Learner response to an instructor question, instruction, or assigned task; correctness does not affect this label. |
| `SP` | Student prompt | General learner-initiated prompt or interactional initiative. |
| `SP:I` | Student instruction | Directs another participant to perform an action. |
| `SP:IQ` | Student information question | Requests new information. |
| `SP:CQ` | Student clarification question | Requests clarification, repetition, explanation, or lexical assistance (e.g., *¿Cómo se dice…?*). |
| `CM` | Classroom management | Learner speech concerning logistics, technology, or participation. |
| `CoM` | Conversation management | Minimal backchannels or expressions regulating conversation. |

### Feedback response and uptake (`R:*`)

| Label | Full name | Operational definition |
|---|---|---|
| `R:S` | Successful repair | Learner resolves the **feedback-targeted** linguistic problem, even if other untargeted errors remain. |
| `R:IR` | Incomplete repair | Learner attempts to repair but does not fully resolve the targeted problem. |
| `R:Ack` | Acknowledgement | Learner acknowledges feedback without producing the corrected form. |
| `R:NR` | No response / uptake | No learner uptake occurs before the interaction moves on. |

**Important boundary:** `R:NR` denotes an absence of uptake, but the source guide does not specify how to attach this absence to an existing sentence row. Confirm the corpus's row-assignment convention before reproducing or extending `R:NR` annotations.

**Source-guide qualification:** The detailed guide states that a response in English/native language immediately after teacher feedback should be treated as `PR`, rather than `R`; it also describes self-repair under `R:S`. These edge cases require attention to the original annotation convention and should not be silently generalized to every feedback sequence.

## Independent learner-error labels

Apply error labels **only to learner production** and only when supported by the transcript. Do not label punctuation, capitalization, routine formatting, or apparent ASR errors as learner-language errors.

| Label | Full name | Operational definition | Example |
|---|---|---|---|
| `Er:G` | Grammar error | Exactly one grammatical error (e.g., agreement, verb inflection, syntax, obligatory grammatical element). | *Mi hermana tengo trece años.* |
| `Er:L` | Lexical error | Exactly one incorrect, missing, malformed, or inappropriate lexical item in otherwise Spanish production. | *Yo borrow un libro.* |
| `Er:M` | Multiple errors | More than one observable grammatical and/or lexical error; do not separately add `Er:G` or `Er:L`. | *Mi hermana tengo one perro.* |
| `Er:EU` | English utterance | Entirely or substantially English production **when Spanish is expected**. | *The boy is running.* in a Spanish-description task. |

### Error decision hierarchy

1. If Spanish is expected and the utterance is substantially English, assign `Er:EU`.
2. Otherwise, if **more than one** observable grammatical/lexical error occurs, assign `Er:M`.
3. Otherwise, if exactly one grammatical error occurs, assign `Er:G`.
4. Otherwise, if exactly one lexical error occurs, assign `Er:L`.
5. Otherwise, leave `error_labels` empty.

English is **not automatically erroneous**: English may be appropriate for classroom management, permitted by the instructor, or required by the task. An isolated English word in otherwise Spanish production is generally `Er:L`, rather than `Er:EU`. Distinguish learner errors from ASR artifacts conservatively.

## Common ambiguities

| Distinction | Apply this rule |
|---|---|
| `P:*` vs. `F:*` | New learner production/task → prompt; response to learner production or correction → feedback. |
| `PR` vs. `R:*` | Ordinary response to an instructor prompt → `PR`; uptake within a feedback sequence → `R:*` (subject to the source guide's language qualification). |
| `F:Pr` vs. `RN` | Evaluation of performance → praise; reaction to content/emotion → reaction. |
| `F:Ack` vs. `CoM` | Acknowledgement of learner form as pedagogical feedback → `F:Ack`; minimal conversational backchannel → `CoM`. |
| `CM` vs. `CoM` | Lesson logistics/technology/participation → `CM`; minimal flow-regulating expression → `CoM`. |
| `Er:L` vs. `Er:EU` | Isolated non-Spanish lexical item → `Er:L`; substantially English response when Spanish is expected → `Er:EU`. |

## Interpretation and reproducibility

- The `labels` and `error_labels` fields are independent: a learner row can be `PR` and `Er:G` simultaneously.
- Annotations are **row-level**, even when their interpretation depends on preceding or following turns; they are not automatically verified feedback episodes.
- Annotated event frequencies should not be interpreted as measures of learning gains, proficiency, or instructional effectiveness.
- Consult the paper and the original detailed guide for adjudication procedures, rare edge cases, and corpus-specific decisions.

