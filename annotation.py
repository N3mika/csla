from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from docx import Document
from openai import OpenAI
from tqdm.auto import tqdm


INPUT_DIR = Path(r"-----")
OUTPUT_DIR = Path(r"-----")
INTERMEDIATE_DIR = Path(r"----")

MODEL = "gpt-4.1-2025-04-14"
ROLE_DETECTION_ROWS = 20
BATCH_SIZE = 12
CONTEXT_SIZE = 5
LOOKAHEAD_SIZE = 2
MAX_RETRIES = 3
RETRY_BASE_SECONDS = 5
OVERWRITE_COMPLETED = False

CONTINUE_AFTER_FILE_ERROR = False

SUPPORTED_INPUT_SUFFIXES = {".docx", ".vtt", ".txt"}

ROLE_DETECTION_SYSTEM_PROMPT =  """
You identify the instructor/teacher in a classroom transcript.

Return only valid JSON.
Do not include markdown or commentary.
"""


SYSTEM_PROMPT =  """
You are an expert linguistic annotator for classroom interaction transcripts.

Follow the CSLA annotation guidelines provided by the user exactly.
Annotate only the TARGET ROWS. Use CONTEXT ROWS only to understand the surrounding interaction.

Use the speaker_role field as authoritative when applying speaker-sensitive rules.
Do not invent missing content.
Do not silently correct transcription or ASR errors.
Apply the label hierarchy and priority rules carefully: Feedback has highest priority when an instructor utterance responds to learner production, learner error, or the learner's learning process; Prompt subtypes, including P:D, apply when the instructor elicits learner production or provides task/question details not primarily triggered by learner error; Response/Repair has priority when a learner responds to corrective feedback.
If the evidence is insufficient, use UNK.
Return only valid JSON matching the requested schema.
Do not include markdown, commentary, or explanations outside the JSON.
"""

USER_PROMPT_TEMPLATE = """
You are annotating classroom transcript sentences using the CSLA classroom event annotation system.

CSLA ANNOTATION GUIDE:

{guidelines_summary}

IMPORTANT APPLICATION RULES:

1. Unit of annotation
- Each TARGET ROW is one sentence-level annotation unit.
- Annotate classroom events / communicative functions, not individual words.
- Annotate only what is observable in the transcript.
- Do not silently correct transcript errors.

2. Context use
- CONTEXT ROWS are provided only to help interpret TARGET ROWS.
- CONTEXT ROWS may include both previous and following rows.
- Do not annotate CONTEXT ROWS unless they also appear in TARGET ROWS.
- Use previous rows to identify prior learner production, teacher feedback, task instructions, repair sequences, and learner errors.
- Use following rows only as supporting context, for example to detect uptake/repair after feedback or to clarify whether an utterance functions as feedback.
- Use context to decide labels such as Feedback, Response/Repair, Prompt Response, Prompt, Answer, Error, and Repair.

3. Use speaker_role as authoritative
- Every row includes speaker_role.
- If speaker_role is "instructor":
  - error_labels must be [].
  - Do not assign learner-only labels such as SP, SP:I, SP:IQ, SP:CQ, PR, R:S, R:Ack, R:IR, or R:NR.
- If speaker_role is "learner":
  - Do not assign teacher feedback labels: F:EC, F:R, F:CR, F:EL, F:MF, F:CC, F:Pr, F:Ack, F:NE.
  - Do not assign instructor-only labels such as A, RN, P:I, P:IQ, or P:CQ.
- repair_labels may apply to either instructor or learner rows, but only when conversational repair organization is observable.

4. Three annotation columns
- labels = classroom event classification, including feedback, prompts, instructor answers, reactions, classroom management, conversation management, learner prompt responses, student prompts, and repair outcome labels.
- error_labels = learner language errors only.
- repair_labels = ONLY conversational repair organization labels: R:SI-SR, R:SI-OR, R:OI-SR, R:OI-OR.
- Do not put error labels inside labels.
- Do not put Er:G, Er:L, Er:M, or Er:EU inside labels.
- Do not put classroom event labels inside error_labels.
- Do not put R:S, R:Ack, R:IR, or R:NR inside repair_labels. These four belong in labels.
- Do not put R:SI-SR, R:SI-OR, R:OI-SR, or R:OI-OR inside labels. These four belong in repair_labels.

5. Classroom event labels
- Use labels for classroom event classification.
- Instructor-side labels include A, RN, CoM, CM, P:I, P:IQ, P:CQ, F:EC, F:R, F:CR, F:EL, F:MF, F:CC, F:Pr, F:Ack, F:NE, and UNK.
- Learner-side labels include PR, SP, SP:I, SP:IQ, SP:CQ, CoM, CM, R:S, R:Ack, R:IR, R:NR, and UNK.
- Do not use E as a classroom-event label.
- Do not output bare F. Feedback must always have a subtype.
- Do not output bare R. Learner response/repair to feedback must use R:S, R:Ack, R:IR, or R:NR.
- Avoid bare P for instructor prompts; use P:I, P:IQ, or P:CQ.
- Use SP for learner/student prompts, or SP:I, SP:IQ, SP:CQ if the subtype is clear.

6. Feedback priority
- Feedback is the highest-priority instructor category.
- If an instructor utterance could reasonably be interpreted as Feedback and another label, choose Feedback when it responds to learner production, learner error, expected learner production, or the learner's learning process.
- Feedback may correct, reformulate, evaluate, acknowledge, question, or otherwise respond to learner production.
- Feedback should be based on pedagogical function in context, not grammatical form.
- If a learner asks a lexical-gap question such as "¿Cómo se dice...?" or "How do you say...?", the instructor's supplied word/phrase is usually Feedback, often F:EC, not A.
- If a learner makes an error and the instructor's next relevant utterance supplies, reformulates, evaluates, or guides the target form, choose Feedback.
- If an instructor gives metalinguistic information triggered by learner error or learner production, use F:MF, not a prompt label.
- When an utterance contains an imperative such as "repite", "lee", "di", or "escucha", annotate according to pedagogical purpose, not grammatical form.
- If the imperative serves a corrective-feedback episode, annotate as Feedback, usually F:EC.
- If the imperative initiates a new task unrelated to correction, annotate as P:I.

7. Feedback subtypes
- F:EC = Explicit Correction. The instructor explicitly identifies/corrects a learner error and provides the correct target form. Imperatives such as "di", "repite", or "escucha" can be F:EC when they reinforce the corrected form.
- F:R = Recast. The instructor reformulates the learner's production with the corrected form.
- F:CR = Clarification Request. The instructor requests repetition/clarification because learner production was unclear or problematic.
- F:EL = Elicitation. The instructor tries to elicit the corrected form from the learner without supplying the full target form.
- F:MF = Metalinguistic Feedback. The instructor gives metalinguistic information in response to learner production or learner error.
- F:CC = Confirmation Check. The instructor checks whether a corrected/understood form is what the learner meant.
- F:Pr = Praisal / praise. The instructor positively evaluates learner language, correctness, performance, or class performance.
- F:Ack = Feedback acknowledgement. The instructor acknowledges or repeats the correct form produced by the learner without necessarily praising it.
- F:NE = Negative Evaluation. The instructor negatively evaluates without providing an explicit correction; this should be rare.
- If the instructor reacts to learner content or emotion without evaluating language/performance, use RN, not F:Pr.

8. F:Pr and multi-label completeness
- F:Pr does not block additional labels.
- Always inspect what comes after praise in the same sentence.
- If a sentence starts with praise and then performs another classroom event, include both labels in order.
- Example: "Muy bien ahora inténtalo otra vez." = ["F:Pr", "F:EL"] if the second part elicits repair.
- Example: "Muy bien, puedes darme otro ejemplo?" = ["F:Pr", "P:IQ"] or ["F:Pr", "P:I"] depending on function.

9. Continuation/detail rule
- Do not create a separate label solely because an utterance provides additional detail, elaboration, clarification, or continuation.
- Details and continuations inherit the same functional label as the event they elaborate on.
- Determine which preceding communicative event the utterance continues and retain that event's label.
- Example:
  Teacher: "Provide me at least two Spanish names." = P:I
  Teacher: "By Spanish names I mean names such as Juan or María." = P:I
- Example:
  Learner: "I'm tired, professor."
  Teacher: "I'm sorry." = RN
  Teacher: "You probably worked a lot over the weekend." = RN
- Example:
  Learner: "How many cities should we mention?" = SP:CQ
  Teacher: "Three." = A
  Teacher: "You could also do four." = A
- If the continuation is part of Feedback, keep it as the relevant F subtype.

10. Instructor Answer, Prompt, CM, and CoM
- A = instructor answer to a question that is not part of learner production, feedback, or a classroom task, such as an answer to a classroom-management or clarification question.
- Do not use A when the instructor is filling a learner lexical gap or responding to learner language production; use Feedback.
- P:I = instruction or task direction whose goal is to trigger learner production.
- P:IQ = information-seeking question.
- P:CQ = clarification question.
- A prompt can open a new topic/discourse, including greeting, or finish a topic/discourse, including goodbye, when it elicits learner interaction.
- CM is limited to class organization, technology, participation, learner selection, logistics, classroom environment, or information necessary for class to take place.
- CM is not for instructional content or language production.
- Do not use CM for instructions/questions whose goal is learner production; use P:I, P:IQ, or P:CQ.
- CoM is limited to utterances without semantic content whose primary function is to regulate interaction flow.
- CoM is usually not a full sentence.
- CoM includes fillers, pragmatic markers, discourse markers, backchannels, and minimal acknowledgements such as Mhm, Mm, Ajá, Ah, Oh, Okay, Vale, Claro, Sí when used only as acknowledgement, Ya, Ya veo, Entiendo.
- If you can parse meaningful semantic content, do not use CoM unless it is only functioning as a minimal discourse marker.

11. Learner labels
- PR = Prompt Response. Use when a learner responds to a teacher prompt, question, instruction, or assigned task.
- PR includes learner answers to teacher questions, learner attempts to produce requested language, and learner attempts to perform requested activities.
- PR does not apply to learner responses following teacher feedback; use R:S, R:Ack, R:IR, or R:NR for those.
- SP = Student Prompt. Learner initiates or extends interaction by introducing a new topic, asking another participant a question, or inviting discussion.
- SP:I = learner directs another participant to perform an action or complete a task.
- SP:IQ = learner requests new information.
- SP:CQ = learner requests clarification, repetition, explanation, or asks to fill a lexical gap such as "¿Cómo se dice X?"
- SP:CQ for "how do you say X?" usually has a lexical error in error_labels when X is English and Spanish is expected.
- Learner CM manages lesson organization, technology, participation, or logistics and does not usually need to be in Spanish.
- Learner CoM is limited to backchannels, acknowledgements, discourse continuers, fillers, pragmatic markers, or minimal responses.

12. Response/Repair to Feedback priority
- R:S, R:Ack, R:IR, and R:NR require previous instructor feedback or learner self-repair context.
- Without feedback or self-repair context, do not use R:S, R:Ack, R:IR, or R:NR.
- Response/Repair is the highest-priority learner category when a learner responds to instructor feedback.
- R:S = successful repair. Following an error or corrective feedback, the learner produces a target-like form that fully resolves the targeted error.
- R:S can also apply to self-repair, e.g., "Ellos lean, ellos leen."
- Errors in the original utterance that were not targeted by the feedback do not prevent R:S.
- R:Ack = learner acknowledges feedback but does not produce the corrected form.
- R:IR = learner attempts to respond linguistically to corrective feedback, but the targeted problem is not fully resolved.
- R:NR = no learner uptake/no repair/no response occurs before the interaction moves on.
- Do not use R:NR merely because the learner says they do not know, gives a partial answer, or answers a prompt inadequately.

13. Learner errors
- Learner errors are separate from classroom-event labels.
- Use error_labels only when speaker_role is "learner".
- If speaker_role is "instructor", error_labels must be [].
- Errors describe deviations from target Spanish only.
- Annotate errors only when directly observable in learner production.
- Do not infer intended forms.
- Do not annotate ASR errors.
- Do not annotate English grammar errors as Er:G.
- English is not automatically an error. English is an error only when Spanish production is expected.
- Learner CM utterances do not usually need to be in Spanish; do not count English words in learner CM as an error unless the instructor explicitly expects CM utterances in Spanish or marks it as an error.
- Do not put Er:G, Er:L, Er:M, or Er:EU inside labels.

14. Error-label selection
- Er:EU = English Utterance. Use when Spanish is expected but the learner produces an utterance entirely or substantially in English.
- Er:M = Multiple Errors. Use when a learner utterance contains more than one observable error, whether grammatical, lexical, or a combination.
- Er:G = Grammar Error. Use for a single grammatical error in otherwise interpretable learner production.
- Er:L = Lexical Error. Use for a single lexical error, including an incorrect, missing, or non-Spanish lexical item within otherwise Spanish production.
- Error hierarchy:
  1. If Spanish is expected but the utterance is entirely/substantially English, use ["Er:EU"].
  2. Otherwise, if the utterance contains more than one observable error, use ["Er:M"].
  3. Otherwise, if the utterance contains exactly one grammar error, use ["Er:G"].
  4. Otherwise, if the utterance contains exactly one lexical error, use ["Er:L"].
  5. If none applies, use [].
- Do not combine Er:M with Er:G or Er:L.
- Do not combine Er:EU with Er:G, Er:L, or Er:M.
- Example: "Mi mamá lives en California." = Er:L because one English lexical item is embedded in otherwise Spanish production.
- Example: "The boy is running." when Spanish is expected = Er:EU.
- Example: "Yo goes escuela." = Er:M.
- Example: "Los casa es grande." = Er:M.

15. Conversational repair organization
- repair_labels contains ONLY these four labels:
  R:SI-SR, R:SI-OR, R:OI-SR, R:OI-OR.
- These labels describe who initiated the repair and who completed the repair.
- These labels can apply to learner or instructor rows depending on who performs the relevant repair role.
- If there is no conversational repair organization label, return [].
- These labels can co-exist with labels and error_labels.
- Assign R:SI-SR to the row where the same speaker both initiates and completes the repair.
- Assign R:SI-OR to the row where another person supplies the repair after the original speaker initiated the problem.
- Do not assign R:SI-OR to the learner's "how do you say..." row merely because the learner requested help; assign it to the row where the other person supplies the solution.
- Assign R:OI-SR to the row where another person initiates repair without supplying the target form, and the original speaker independently produces the repair form.
- If another speaker has already supplied the target form, subsequent learner repetition/incorporation is uptake, usually R:S or R:IR, not R:OI-SR.
- Assign R:OI-OR to the row where another person both initiates and supplies the repair/correction.
- Consider the repair episode complete when the targeted trouble is resolved, abandoned, or no longer pursued.
- Do not assign repair_labels to subsequent pedagogical explanation unless it continues the same repair operation.

16. Multiple classroom-event labels
- Ideally assign only one classroom-event label per sentence.
- Multiple labels are allowed ONLY when the sentence contains multiple functional classroom events.
- Do not use multiple labels because of ambiguity.
- If multiple labels are needed, order them according to the order of events in the sentence from left to right.
- Do not stop after assigning F:Pr if the sentence continues with another functional unit.
- Example: "Stella, que tal?" may be CM, P:IQ because calling Stella manages participation and "que tal?" asks a question.
- Example: "Muy bien ahora inténtalo otra vez." should be F:Pr, F:EL.
- If uncertain between labels, choose the best single label and lower the confidence.

17. Confidence
Assign one confidence value:
- HIGH: clear from utterance and context.
- MEDIUM: likely, but context or transcript ambiguity limits certainty.
- LOW: uncertain, but a label is still defensible.
- UNK: cannot determine reliably.

CONTEXT ROWS:
Use these rows only as context.

{context_rows_json}

TARGET ROWS:
Annotate every row below.

{target_rows_json}

OUTPUT REQUIREMENTS:
Return exactly one JSON object with one key: "annotations".

For each TARGET ROW:
- Copy sentence_id exactly.
- Copy turn_number exactly.
- Copy speaker exactly.
- Copy sentence exactly.
- Provide labels as a list of classroom-event labels.
- Provide error_labels as a separate list.
- Provide repair_labels as a separate list containing only R:SI-SR, R:SI-OR, R:OI-SR, or R:OI-OR.
- Provide confidence.
- Provide a short rationale grounded in the transcript and guidelines.

Do not include any rows that are not in TARGET ROWS.
"""

GUIDELINES_SUMMARY = """
CSLA Annotation Guide Summary

General Principles:
- Identify classroom events in the conversation.
- Annotate the communicative function of classroom events, not individual words.
- Annotate only what is observable in the transcript.
- Multiple labels are allowed only when an utterance is too complex and serves multiple functions.
- Keep multiple labels in the order of the events or utterances.
- When an utterance could receive more than one interpretation, annotate according to its primary communicative function: what the speaker is trying to accomplish.
- Do not annotate based only on grammatical form. For example, an imperative can be Feedback or Prompt depending on its pedagogical purpose.
- Secondary labels should only be added when a second instructional function is independently observable and cannot be separated into another utterance.
- Details, elaborations, clarifications, and continuations receive the same functional label as the event they elaborate on.
- Do not create a separate label only because an utterance provides additional detail.
- Use UNK when the function cannot be determined reliably.
- Code-switching is not annotated.

Input Role Field:
- Each row contains speaker_role.
- Treat speaker_role as authoritative.
- If speaker_role is instructor, error_labels must be [].
- If speaker_role is learner, do not assign instructor feedback labels such as F:EC, F:R, F:CR, F:EL, F:MF, F:CC, F:Pr, F:Ack, or F:NE.
- repair_labels may apply to either instructor or learner rows when conversational repair organization is observable.

Output Columns:
Column 1: labels = classroom event classification.
Column 2: error_labels = learner errors.
Column 3: repair_labels = conversational repair organization only.

Important distinction:
- labels includes classroom events and repair outcome labels: R:S, R:Ack, R:IR, R:NR.
- repair_labels includes only conversational repair organization labels: R:SI-SR, R:SI-OR, R:OI-SR, R:OI-OR.
- error_labels includes only learner language errors: Er:G, Er:L, Er:M, Er:EU.

Instructor Classroom Event Labels:

A = Answer.
Use A for instructor answers to learner questions that are not feedback and are not part of correcting learner production.
A can answer classroom-management questions, clarification questions, or information-seeking questions.
Example:
Learner: "Do you hear me, professor?"
Instructor: "Yes, I do." = A

Example:
Learner: "How many cities should we mention?"
Instructor: "Three." = A
Instructor: "You could also do four." = A

Do not use A when the instructor utterance responds to learner error, learner production, or the learner's learning process; use Feedback instead.
Do not use A for learner rows.

RN = Reaction.
Responds to the meaning, content, or emotional aspect of the learner's previous contribution without correcting language, assigning a new task, or evaluating linguistic accuracy.
Example:
Learner: "I'm tired, professor."
Instructor: "Oh, I'm sorry." = RN
Instructor: "You probably worked a lot on the weekend." = RN

Use RN when the instructor reacts to learner content or emotion.
Use F:Pr when the instructor positively evaluates learner language, correctness, performance, or class performance.

CoM = Conversation Management.
CoM is limited to fillers or discourse markers only.
CoM utterances do not have clear semantic content and mainly regulate, maintain, or facilitate interaction flow.
CoM is usually not a full sentence.
Examples: Mhm, Mm, Ajá, Ah, Oh, Okay, Vale, Claro, Sí as acknowledgement only, Ya, Ya veo, Entiendo.
Questions that only check agreement with instructions can be CoM:
"Now read this. Ok?" / "Bien?"
Short discourse markers indicating start/end of a task or topic can be CoM when they only regulate flow:
"Muy bien" / "Alright" before moving on.

Do not use CoM for full semantic responses, information-seeking questions, instructional prompts, feedback, prompt responses, or task content.

CM = Classroom Management.
Manages class organization, technology, participation, learner selection, lesson logistics, classroom environment, or information necessary for class to take place.
Examples:
"¿Me escuchan?"
"Voy a compartir la pantalla."
"Stella, your turn."
"Tomorrow there will be a test."
"Open the windows to put some fresh air in."

CM is not for instructional content or language production.
Do not use CM for instructions/questions whose goal is learner production; use P:I, P:IQ, or P:CQ.

Prompt Labels:

P:I = Instruction.
Gives directions or assigns a learning task with the goal of triggering learner production.
Details, examples, clarifications, or continuations of the same instruction are also P:I.
Examples:
"Describe el personaje." = P:I
"Can you tell me three activities you like to do?" = P:I
"Provide me at least two Spanish names." = P:I
"By Spanish names I mean names such as Juan or María." = P:I

Greeting/goodbye sequences that elicit learner language may be prompts.

P:IQ = Information-seeking question.
Use P:IQ when the instructor asks a question to elicit learner information or learner language.
Details, examples, clarifications, or continuations of the same question are also P:IQ.
Examples:
"How old are you?" = P:IQ
"How are you doing today?" = P:IQ
"Cuál es el tema de la unidad?" = P:IQ

P:CQ = Clarification question.
Use P:CQ when the instructor requests clarification about what the learner said or meant, without necessarily giving feedback.
Example:
"Do you mean zyx?" = P:CQ

Feedback Labels:
Feedback responds to learners' learning process, usually learner production, learner error, or learner language development.
Whenever feedback is assigned, use one subtype.
Feedback is the highest-priority instructor category: whenever an instructor utterance responds to learner production, learner error, or the learner's learning process, prioritize Feedback over A, RN, CM, CoM, P:I, P:IQ, or P:CQ.
Feedback labels should normally be assigned only to instructor rows.

Details, explanations, examples, repetitions, or continuations that elaborate a feedback move should receive the same appropriate Feedback label.
Do not label feedback-related explanations as prompt details.

When an utterance contains an imperative such as "repite", "lee", "di", or "escucha", annotate according to pedagogical purpose rather than grammatical form.
- If the imperative serves a corrective-feedback episode, annotate as Feedback.
- If the imperative initiates a new task, annotate as P:I.

F:EC = Explicit Correction.
The instructor explicitly identifies or corrects a learner error by providing the correct target form.
The correction is overt and leaves no ambiguity about the intended linguistic form.
Imperatives such as "di", "repite", or "escucha" can be F:EC when they reinforce the corrected form.
Example:
Student: "He go."
Instructor: "No. Di 'He goes'." = F:EC

F:R = Recast.
The instructor reformulates the learner's production with the corrected form.
Example:
Student: "Mi hermana tengo trece años."
Instructor: "Ah, tu hermana tiene trece años." = F:R

F:CR = Clarification Request.
The instructor requests repetition/clarification because learner production was unclear or problematic.
Example:
"Perdón, ¿puedes repetir?" = F:CR

F:EL = Elicitation.
The instructor tries to elicit the corrected form from the learner without supplying the full target form.
Example:
Student: "Mi hermana tengo..."
Instructor: "Tu hermana..." = F:EL

F:MF = Metalinguistic Feedback.
The instructor gives metalinguistic information in response to learner production or learner error.
Example:
"Recuerda la tercera persona: tiene." = F:MF

F:CC = Confirmation Check.
The instructor checks whether a corrected/understood form is what the learner meant.
Example:
"¿Quieres decir que tu hermana tiene trece años?" = F:CC

F:Pr = Praisal / praise.
Use when the instructor positively evaluates learner language, correctness, performance, or class performance.
F:Pr can refer to class performance in general even when no adjacent learner utterance is present.
Examples:
"Muy bien!" after a correct learner answer = F:Pr
"Es correcto!" = F:Pr
"Good job!" / "Buen trabajo!" = F:Pr

F:Pr does not block additional labels.
Always inspect what comes after praise in the same sentence.
If a sentence starts with praise and then performs another classroom event, include both labels in order.
Examples:
"Muy bien ahora inténtalo otra vez." = labels: F:Pr, F:EL
"Muy bien, puedes darme otro ejemplo?" = labels: F:Pr, P:IQ or F:Pr, P:I depending on function.

F:Ack = Feedback Acknowledgement.
Use when the instructor acknowledges, accepts, confirms, or repeats a learner's correct or improved production without adding explicit praise.
Example:
Learner: "Ellos leen."
Instructor: "Leen." = F:Ack

F:NE = Negative Evaluation.
Use when the instructor negatively evaluates without providing an explicit correction.
Example:
"No, eso no está bien." = F:NE
F:NE differs from F:EC because F:EC provides a correction. F:NE should be rare.

Learner Classroom Event Labels:

PR = Prompt Response.
Use PR for learner utterances produced in response to an instructor prompt, question, instruction, or assigned task.
PR replaces learner A and learner T.
PR applies whether the learner response is complete, incomplete, correct, incorrect, short, or extended, as long as it responds to a prompt/task rather than feedback.
Examples:
Instructor: "¿Cómo estás?"
Learner: "Estoy bien." = PR

Instructor: "¿Cuál es tu comida favorita?"
Learner: "Tacos." = PR

Instructor: "Completa la oración."
Learner: "Ellos leen." = PR

Do not use PR when the learner is responding to corrective feedback; use R:S, R:Ack, R:IR, or R:NR.

SP = Student Prompt.
Initiates or extends the interaction by introducing a new topic, asking another participant a question, or inviting discussion.
Student prompts are not responses to teacher feedback.
Examples:
"A mí me gusta viajar. ¿Y a vosotros?" = SP
"Profesor, ¿qué piensa usted?" = SP

SP:I = Student prompt instruction.
Learner directs another participant to perform an action or complete a task.

SP:IQ = Student information-seeking question.
Learner requests new information.

SP:CQ = Student clarification question.
Learner requests clarification, repetition, explanation, or help with a language gap.
SP:CQ can be used when a learner asks to fill a lexical gap, such as "¿Cómo se dice X?" or "How do you say X in Spanish?"
When the learner uses an English lexical item because they are asking how to say it in Spanish, this clarification question may also have a lexical error in error_labels if Spanish was expected.

Response/Repair to Feedback:
Use repair outcome labels only after instructor feedback.
Without instructor feedback, there is no Response/Repair.
Do not output bare R.
Response/Repair is the priority category when a learner responds to instructor feedback, even if the utterance could also look like PR, CM, or CoM.

R:S = Successful Repair.
Following corrective feedback or self-repair, the learner produces a target-like form that resolves the targeted problem.
Errors in the original utterance that were not targeted by the feedback do not affect R:S.
Example:
Student: "Yo tengo uno hermana que vivir en Tucson."
Instructor: "Una hermana."
Student: "Una hermana." = R:S
The instructor targeted "uno hermana"; the learner repaired the targeted error.

Example:
Instructor: "Di tiene."
Learner: "Tiene." = R:S

Example:
Learner: "Ellos lean, ellos leen." = R:S with repair_labels: R:SI-SR

R:Ack = Feedback acknowledged but no repair.
Learner acknowledges feedback but does not produce the corrected form.
Examples:
Instructor: "No. Se dice tiene."
Learner: "Sí." / "Vale." / "Entiendo." = R:Ack

R:IR = Incomplete or unsuccessful repair.
The learner attempts to respond linguistically to corrective feedback, but the targeted problem is not fully resolved.
This includes partial correction, continued error, or incorrect attempted repair.
Example:
Instructor: "Di 'Tengo una hija'."
Learner: "Tengo." = R:IR

R:NR = No uptake / no repair / no response.
No learner utterance responding to the corrective feedback occurs before the interaction moves on.
Use for silence or topic change after feedback.
Do not use R:NR merely because a learner says they do not know, gives a partial answer, or answers a prompt inadequately.

CoM = Conversation Management.
Learner backchannels, acknowledgements, discourse continuers, fillers, pragmatic markers, or minimal responses.
Examples:
Mhm, Mm, Ajá, Okay, Vale, Sí as acknowledgement only, Ya veo, Entiendo.

CM = Classroom Management.
Learner manages lesson organization, technology, participation, or logistics rather than contributing to instructional content.
Learner CM does not usually need to be in Spanish.
Examples:
"No puedo escuchar." = CM
"¿Puede repetir?" = CM
"No veo la pantalla." = CM
"Professor, my headphones do not work." = CM

Learner Errors:
Learner errors are independent from classroom event labels and go in error_labels.
Use error_labels only when speaker_role is learner.
If speaker_role is instructor, error_labels must be [].
Errors describe deviations from target Spanish only.
Annotate errors only when directly observable in learner production.
Do not infer intended forms.
Do not annotate ASR errors.
Do not annotate English grammar errors as Er:G.
Learner CM utterances do not usually need to be in Spanish; do not count English words in learner CM as Er:L or Er:EU unless the instructor explicitly expects CM utterances in Spanish or marks it as an error.

Er:G = Grammar Error.
Use when the learner utterance contains exactly one Spanish grammar error.
Grammar errors involve Spanish grammatical structure, including morphology, syntax, agreement, word order, verb conjugation, tense/aspect/mood, gender agreement, number agreement, article usage, pronoun usage, prepositions, case-related errors, or missing obligatory grammatical elements.
Examples:
"Mi hermana tengo trece años." = Er:G
"Ella es cansado." = Er:G
"Yo comer pizza ayer." = Er:G
"Voy escuela." = Er:G
"Los casa son grandes." = Er:G

Do not annotate punctuation, capitalization, spelling mistakes that do not affect lexical choice, ASR transcription errors, or English grammar as Spanish grammar errors.
Example:
"mi hermana tengo trece años" without punctuation is not Er:G because of the missing period; it is Er:G only because of incorrect verb agreement.

Er:L = Lexical Error.
Use when the learner utterance contains exactly one lexical error.
Lexical errors include incorrect Spanish lexical item, incorrect lexical meaning, omitted required lexical item, wrong lexical form, or an individual English/non-Spanish lexical item embedded in otherwise Spanish production when Spanish is expected.
Examples:
"Yo borrow un libro." = Er:L
"Ella es una doctor." = Er:L
"Necesito un ___." = Er:L if a required noun is omitted.
Teacher: "¿Cómo se dice dog en español?"
Learner: "Dog." = Er:L

Er:EU = English Utterance.
Use when the learner produces an entire or substantially English utterance when Spanish production is expected.
Example:
Instructor: "Describe la imagen en español."
Learner: "The boy is running." = Er:EU

Er:M = Multiple Errors.
Use when the learner utterance contains more than one error of the same type, or more than two total errors.
Do not combine Er:M with Er:G, Er:L, or Er:EU.

Multiple Error Labels:
- If the learner utterance contains exactly two errors and one is grammar and one is lexical, use both labels in the order the errors occur, e.g., ["Er:G", "Er:L"] or ["Er:L", "Er:G"].
- If the learner utterance contains more than one error of the same type, or more than two total errors, use ["Er:M"].
- Do not use E:M.

Conversational Repair Organization:
These labels go ONLY in repair_labels.

R:SI-SR = Self-initiated self-repair.
The same speaker notices their own problem and fixes it.
Assign R:SI-SR to the row where the same speaker completes the repair.
Example:
Learner: "Tengo... perdón, tiene trece años." = R:SI-SR

R:SI-OR = Self-initiated other-repair.
The original speaker signals a problem, but another person supplies the solution.
Assign R:SI-OR to the row where the other person supplies the repair/solution, not merely to the learner's request-for-help row.
Example:
Learner: "¿Cómo se dice...?"
Instructor: "Diversión." = R:SI-OR

R:OI-SR = Other-initiated self-repair.
Another person initiates repair without supplying the target form, and the original speaker independently produces the repair form.
Assign R:OI-SR to the row where the original speaker completes the repair.
Example:
Instructor: "Tu hermana...?"
Learner: "Tiene trece años." = R:OI-SR

If another speaker has already supplied the target form, subsequent learner repetition or incorporation of that form is uptake, usually R:S or R:IR, not R:OI-SR.

R:OI-OR = Other-initiated other-repair.
Another person identifies the problem and supplies the correction.
Assign R:OI-OR to the row where the other person supplies the correction.
Example:
Learner: "Mi hermana tengo trece años."
Instructor: "Tu hermana tiene trece años." = R:OI-OR

Consider the repair episode complete when the targeted trouble is resolved, abandoned, or no longer pursued.
Do not assign repair_labels to subsequent pedagogical detail unless it continues the same repair operation.
Independently annotate learner uptake following instructor feedback as R:S, R:Ack, R:IR, or R:NR.

Continuation and Detail Rule:
- Details, elaborations, clarifications, and continuations inherit the functional label of the event they elaborate on.
- Do not use a separate detail label.
Examples:
Instructor: "Provide me at least two Spanish names." = P:I
Instructor: "By Spanish names I mean names such as Juan or María." = P:I
Learner: "I'm tired, professor." = PR or SP depending on context
Instructor: "Oh, I'm sorry." = RN
Instructor: "You probably worked a lot on the weekend." = RN
Learner: "How many cities should we mention?" = SP:CQ
Instructor: "Three." = A
Instructor: "You could also do four." = A

Multiple Labels:
- Multiple labels inside the same column should be reduced as much as possible.
- Ideally one classification per utterance applies.
- Use multiple labels only when the sentence contains multiple classroom events because segmentation is imperfect.
- Keep label order according to event order.
- Do not stop after assigning F:Pr if the sentence continues with another functional unit.
Examples:
"Muy bien ahora inténtalo otra vez." = labels: F:Pr, F:EL
"Tu botella de agua, excelente." = labels: F:R, F:Pr
"Stella, que tal?" = labels: CM, P:IQ
"The students who have not given consent will not be used." = labels: CM
"Estoy cansado." as prompt response with gender error = labels: PR; error_labels: Er:G
"Estoy bien." in response to "How are you doing today?" = labels: PR
"Estoy cansada." after previous incorrect form = labels: R:S; repair_labels: R:SI-SR if self-initiated self-repair is observable

Annotation Workflow:
1. Read the surrounding interaction.
2. Use speaker_role to identify instructor vs learner.
3. Assign classroom event labels in labels.
4. Prioritize Feedback when an instructor responds to learner production, learner error, or learning process.
5. Use continuation/detail inheritance instead of creating separate detail labels.
6. Prioritize Response/Repair when a learner responds to corrective feedback.
7. Use PR for learner responses to instructor prompts, questions, instructions, or assigned tasks.
8. Use multiple labels only for multiple classroom events.
9. Assign learner errors in error_labels only when speaker_role is learner.
10. Assign conversational repair organization labels in repair_labels.
11. Assign confidence HIGH / MEDIUM / LOW / UNK.
12. Use UNK rather than guessing.
"""


ANNOTATION_JSON_SCHEMA = {
    "name": "csla_batch_annotations",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "annotations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sentence_id": {
                            "type": "string",
                            "description": "Unique sentence ID from the input row.",
                        },
                        "turn_number": {
                            "type": "integer",
                            "description": "Transcript turn number copied from the input row.",
                        },
                        "speaker": {
                            "type": "string",
                            "description": "Speaker name copied from the input row.",
                        },
                        "sentence": {
                            "type": "string",
                            "description": "Sentence text copied exactly from the input row.",
                        },
                        "labels": {
                            "type": "array",
                            "description": "Classroom-event labels only. Includes instructor labels, learner prompt response label PR, and repair outcome labels R:S, R:Ack, R:IR, R:NR. Multiple labels only when the sentence contains multiple functional classroom events.",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "A", "RN", "CoM", "CM", "P:I", "P:IQ",
                                    "P:CQ", "F:EC", "F:R", "F:CR", "F:EL",
                                    "F:MF", "F:CC", "F:Pr", "F:Ack", "F:NE",
                                    "SP", "SP:I", "SP:IQ", "SP:CQ", "PR",
                                    "R:S", "R:Ack", "R:IR", "R:NR", "UNK",
                                ],
                            },
                        },
                        "error_labels": {
                            "type": "array",
                            "description": "Separate learner error labels. Empty list if no learner error is present. Use Er:M alone for multiple errors.",
                            "items": {
                                "type": "string",
                                "enum": ["Er:G", "Er:L", "Er:M", "Er:EU"],
                            },
                        },
                        "repair_labels": {
                            "type": "array",
                            "description": "Conversational repair organization labels only. Empty list if no conversational repair organization label is present.",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "R:SI-SR", "R:SI-OR", "R:OI-SR", "R:OI-OR"
                                ],
                            },
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["HIGH", "MEDIUM", "LOW", "UNK"],
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Brief explanation grounded in the transcript and guidelines.",
                        },
                    },
                    "required": [
                        "sentence_id", "turn_number", "speaker", "sentence",
                        "labels", "error_labels", "repair_labels", "confidence",
                        "rationale",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["annotations"],
        "additionalProperties": False,
    },
}


LOGGER = logging.getLogger("csla_batch")


def elapsed_text(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes:d}m {seconds:02d}s"
    return f"{seconds:d}s"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
    temp_path.replace(path)


def atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    df.to_csv(temp_path, index=False, encoding="utf-8-sig")
    temp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prompt_fingerprint() -> str:
    text = "\n---PROMPT---\n".join(
        [
            ROLE_DETECTION_SYSTEM_PROMPT,
            SYSTEM_PROMPT,
            USER_PROMPT_TEMPLATE,
            GUIDELINES_SUMMARY,
            inspect.getsource(build_role_detection_prompts),
        ]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    LOGGER.addHandler(console)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)


def split_into_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    final_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for part in re.split(r"\s*,?\s*(?=[¿¡])", sentence):
            part = part.strip()
            if part:
                final_sentences.append(part)
    return final_sentences


CUE_PATTERN = re.compile(
    r"""
    (?P<source_turn_number>\d+)\s+
    (?P<start_time>\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*
    (?P<end_time>\d{2}:\d{2}:\d{2}\.\d{3})\s+
    (?P<line>.*?)
    (?=\n\s*\d+\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*-->|$)
    """,
    re.VERBOSE | re.DOTALL,
)


def remove_curly_brace_comments(text: str) -> str:
    return re.sub(r"\{[^{}]*\}", "", str(text))


def collect_speakers_from_cue_starts(raw_text: str) -> list[str]:
    text = raw_text.replace("\u00a0", " ").strip()
    text = remove_curly_brace_comments(text)
    text = re.sub(r"^\s*WEBVTT\s*", "", text, flags=re.IGNORECASE)
    speakers: set[str] = set()
    for match in CUE_PATTERN.finditer(text):
        line = remove_curly_brace_comments(match.group("line").strip())
        line = re.sub(r"\s+", " ", line).strip()
        start_match = re.match(r"^([^:]{1,80})\s*:", line)
        if start_match:
            speaker = start_match.group(1).strip()
            if speaker and len(speaker.split()) <= 8:
                speakers.add(speaker)
    return sorted(speakers)


def build_known_speaker_pattern(known_speakers: list[str]) -> re.Pattern[str] | None:
    if not known_speakers:
        return None
    escaped = [re.escape(s) for s in sorted(known_speakers, key=len, reverse=True)]
    return re.compile(r"(?P<speaker>" + "|".join(escaped) + r")\s*:")


def split_speaker_blocks(line: str, known_speakers: list[str]) -> list[dict[str, Any]]:
    line = re.sub(r"\s+", " ", str(line)).strip()
    speaker_pattern = build_known_speaker_pattern(known_speakers)
    matches = list(speaker_pattern.finditer(line)) if speaker_pattern else []
    if not matches:
        return [{"speaker": None, "utterance": line}]

    blocks = []
    for index, match in enumerate(matches):
        utterance_start = match.end()
        utterance_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        utterance = line[utterance_start:utterance_end].strip()
        if utterance:
            blocks.append(
                {"speaker": match.group("speaker").strip(), "utterance": utterance}
            )
    return blocks


def parse_webvtt_transcript(raw_text: str, extra_speakers: list[str] | None = None) -> pd.DataFrame:
    rows = []
    text = raw_text.replace("\u00a0", " ").strip()
    text = remove_curly_brace_comments(text)
    text = re.sub(r"^\s*WEBVTT\s*", "", text, flags=re.IGNORECASE)
    known_speakers = collect_speakers_from_cue_starts(raw_text)
    if extra_speakers:
        known_speakers = sorted(set(known_speakers) | set(extra_speakers))
    LOGGER.info("Detected speakers: %s", ", ".join(known_speakers) or "none")

    new_turn_number = 1
    for match in CUE_PATTERN.finditer(text):
        line = remove_curly_brace_comments(match.group("line").strip())
        line = re.sub(r"\s+", " ", line).strip()
        for block in split_speaker_blocks(line, known_speakers):
            for sentence in split_into_sentences(block["utterance"]):
                rows.append(
                    {
                        "turn_number": new_turn_number,
                        "source_turn_number": int(match.group("source_turn_number")),
                        "start_time": match.group("start_time"),
                        "end_time": match.group("end_time"),
                        "speaker": block["speaker"],
                        "sentence": sentence,
                    }
                )
            new_turn_number += 1

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No WebVTT cues were parsed from this transcript.")
    df.insert(0, "sentence_id", [str(i) for i in range(1, len(df) + 1)])
    return df


def read_transcript(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        document = Document(path)
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return path.read_text(encoding="utf-8-sig")


def format_initial_rows_for_role_detection(df: pd.DataFrame, n: int = 20) -> str:
    sample = df.head(n)[["turn_number", "speaker", "sentence"]].to_dict(
        orient="records"
    )
    return json.dumps(sample, ensure_ascii=False, indent=2)


def build_role_detection_prompts(
    speakers: list[str], sample_rows_json: str, n_rows: int
) -> tuple[str, str]:
    system_prompt = ROLE_DETECTION_SYSTEM_PROMPT

    user_prompt = f"""
The transcript has these speakers:

{json.dumps(speakers, ensure_ascii=False, indent=2)}

Here are the first {n_rows} transcript rows:

{sample_rows_json}

Task:
Identify which speaker is the instructor/teacher/tutor.

Use evidence such as:
- who gives instructions,
- who asks students questions,
- who manages the session,
- who addresses multiple students,
- who explains lesson content.

Return exactly this JSON structure:

{{
  "instructor_speaker": "speaker name exactly as listed",
  "confidence": "HIGH/MEDIUM/LOW",
  "rationale": "brief reason"
}}
"""

def detect_instructor_speaker(
    client: OpenAI,
    df: pd.DataFrame,
    model: str = MODEL,
    n_rows: int = ROLE_DETECTION_ROWS,
) -> tuple[str, dict[str, Any]]:
    speakers = sorted(df["speaker"].dropna().unique().tolist())
    if not speakers:
        raise ValueError("No speaker names were detected; instructor detection cannot run.")
    sample_rows_json = format_initial_rows_for_role_detection(df, n=n_rows)
    system_prompt, user_prompt = build_role_detection_prompts(
        speakers, sample_rows_json, n_rows
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        top_p=1,
        max_completion_tokens=500,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    instructor = result["instructor_speaker"]
    if instructor not in speakers:
        raise ValueError(
            f"Model returned instructor {instructor!r}, not one of {speakers!r}."
        )
    LOGGER.info(
        "Detected instructor: %s | confidence: %s | rationale: %s",
        instructor,
        result.get("confidence"),
        result.get("rationale"),
    )
    return instructor, result


def format_rows_for_prompt(df_chunk: pd.DataFrame) -> str:
    rows = []
    for _, row in df_chunk.iterrows():
        item = {
            "sentence_id": str(row["sentence_id"]),
            "turn_number": int(row["turn_number"]),
            "source_turn_number": (
                int(row["source_turn_number"])
                if "source_turn_number" in row and pd.notna(row["source_turn_number"])
                else None
            ),
            "start_time": str(row["start_time"]),
            "end_time": str(row["end_time"]),
            "speaker": str(row["speaker"]) if pd.notna(row["speaker"]) else None,
            "speaker_role": (
                str(row["speaker_role"])
                if "speaker_role" in row and pd.notna(row["speaker_role"])
                else None
            ),
            "sentence": str(row["sentence"]),
        }
        if "context_position" in row and pd.notna(row["context_position"]):
            item["context_position"] = str(row["context_position"])
        rows.append(item)
    return json.dumps(rows, ensure_ascii=False, indent=2)


def call_gpt_for_annotations(
    client: OpenAI,
    context_df: pd.DataFrame,
    target_df: pd.DataFrame,
    model: str = MODEL,
) -> dict[str, Any]:
    prompt_text = USER_PROMPT_TEMPLATE.format(
        guidelines_summary=GUIDELINES_SUMMARY,
        context_rows_json=format_rows_for_prompt(context_df),
        target_rows_json=format_rows_for_prompt(target_df),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        temperature=0,
        top_p=1,
        max_completion_tokens=4000,
        response_format={
            "type": "json_schema",
            "json_schema": ANNOTATION_JSON_SCHEMA,
        },
    )
    return json.loads(response.choices[0].message.content)


def call_with_retries(
    client: OpenAI,
    context_df: pd.DataFrame,
    target_df: pd.DataFrame,
    model: str = MODEL,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    for attempt in range(1, max_retries + 1):
        try:
            result = call_gpt_for_annotations(client, context_df, target_df, model)
            annotations = result.get("annotations", [])
            if len(annotations) != len(target_df):
                raise ValueError(
                    f"Expected {len(target_df)} annotations, got {len(annotations)}."
                )
            expected_ids = target_df["sentence_id"].astype(str).tolist()
            actual_ids = [str(item.get("sentence_id")) for item in annotations]
            if actual_ids != expected_ids:
                raise ValueError(
                    f"Returned sentence IDs do not match. Expected {expected_ids}; "
                    f"received {actual_ids}."
                )
            return result
        except Exception as exc:
            LOGGER.exception("API attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt == max_retries:
                break
            wait_seconds = RETRY_BASE_SECONDS * attempt
            LOGGER.info("Retrying in %s...", elapsed_text(wait_seconds))
            time.sleep(wait_seconds)
    raise RuntimeError("API call failed after maximum retries.")


def make_manifest(input_path: Path) -> dict[str, Any]:
    return {
        "input_file": input_path.name,
        "input_sha256": sha256_file(input_path),
        "model": MODEL,
        "batch_size": BATCH_SIZE,
        "context_size": CONTEXT_SIZE,
        "lookahead_size": LOOKAHEAD_SIZE,
        "role_detection_rows": ROLE_DETECTION_ROWS,
        "prompt_fingerprint": prompt_fingerprint(),
    }


def ensure_compatible_manifest(input_path: Path, work_dir: Path) -> None:
    manifest_path = work_dir / "run_manifest.json"
    current = make_manifest(input_path)
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
        mismatches = {
            key: (existing.get(key), value)
            for key, value in current.items()
            if existing.get(key) != value
        }
        if mismatches:
            details = "; ".join(
                f"{key}: saved={old!r}, current={new!r}"
                for key, (old, new) in mismatches.items()
            )
            raise RuntimeError(
                "Existing checkpoints were created with different input/settings. "
                f"Move or rename this intermediate folder before starting a new run. {details}"
            )
    else:
        atomic_write_json({**current, "created_at_utc": utc_now()}, manifest_path)


def load_or_create_processed(input_path: Path, work_dir: Path) -> pd.DataFrame:
    processed_path = work_dir / f"{input_path.stem}_processed.csv"
    if processed_path.exists():
        LOGGER.info("Loading preprocessing checkpoint: %s", processed_path.name)
        return pd.read_csv(processed_path, dtype={"sentence_id": str})

    stage_start = time.perf_counter()
    raw_transcript = read_transcript(input_path)
    df = parse_webvtt_transcript(raw_transcript)
    atomic_write_csv(df, processed_path)
    LOGGER.info(
        "Preprocessing saved: %s rows in %s",
        len(df),
        elapsed_text(time.perf_counter() - stage_start),
    )
    return df


def load_or_assign_roles(
    client: OpenAI, input_path: Path, work_dir: Path, df: pd.DataFrame
) -> pd.DataFrame:
    roles_path = work_dir / f"{input_path.stem}_processed_with_roles.csv"
    role_info_path = work_dir / f"{input_path.stem}_instructor_detection.json"
    if roles_path.exists():
        LOGGER.info("Loading speaker-role checkpoint: %s", roles_path.name)
        roles_df = pd.read_csv(roles_path, dtype={"sentence_id": str})
        if roles_df["sentence_id"].tolist() != df["sentence_id"].astype(str).tolist():
            raise ValueError("Speaker-role checkpoint sentence IDs do not match preprocessing.")
        return roles_df

    stage_start = time.perf_counter()
    instructor, detection_info = detect_instructor_speaker(client, df)
    roles_df = df.copy()
    roles_df["speaker_role"] = roles_df["speaker"].apply(
        lambda value: "instructor" if value == instructor else "learner"
    )
    atomic_write_json(
        {
            "input_file": input_path.name,
            "instructor_speaker": instructor,
            "detection": detection_info,
            "saved_at_utc": utc_now(),
        },
        role_info_path,
    )
    atomic_write_csv(roles_df, roles_path)
    LOGGER.info(
        "Speaker roles saved in %s",
        elapsed_text(time.perf_counter() - stage_start),
    )
    return roles_df


def batch_slices(row_count: int) -> list[tuple[int, int]]:
    return [
        (start, min(start + BATCH_SIZE, row_count))
        for start in range(0, row_count, BATCH_SIZE)
    ]


def validate_saved_batch(
    result: dict[str, Any], target_df: pd.DataFrame, batch_path: Path
) -> list[dict[str, Any]]:
    annotations = result.get("annotations", [])
    expected_ids = target_df["sentence_id"].astype(str).tolist()
    actual_ids = [str(item.get("sentence_id")) for item in annotations]
    if len(annotations) != len(target_df) or actual_ids != expected_ids:
        raise ValueError(
            f"Checkpoint {batch_path.name} is incomplete or does not match the transcript."
        )
    return annotations


def annotate_with_batch_checkpoints(
    client: OpenAI, input_path: Path, work_dir: Path, df: pd.DataFrame
) -> pd.DataFrame:
    batches_dir = work_dir / "annotation_batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    slices = batch_slices(len(df))
    all_annotations: list[dict[str, Any]] = []

    for batch_number, (start, end) in enumerate(
        tqdm(slices, desc=f"{input_path.stem}: annotation batches"), start=1
    ):
        batch_path = batches_dir / f"{input_path.stem}_batch_{batch_number:04d}.json"
        target_df = df.iloc[start:end].copy()

        if batch_path.exists():
            with batch_path.open("r", encoding="utf-8") as handle:
                saved = json.load(handle)
            annotations = validate_saved_batch(saved, target_df, batch_path)
            all_annotations.extend(annotations)
            LOGGER.info(
                "Batch %d/%d already saved; skipping API call.",
                batch_number,
                len(slices),
            )
            continue

        batch_start = time.perf_counter()
        context_start = max(0, start - CONTEXT_SIZE)
        context_end = min(len(df), end + LOOKAHEAD_SIZE)
        previous_context = df.iloc[context_start:start].copy()
        following_context = df.iloc[end:context_end].copy()
        previous_context["context_position"] = "previous"
        following_context["context_position"] = "following"
        context_df = pd.concat(
            [previous_context, following_context], ignore_index=True
        )

        result = call_with_retries(client, context_df, target_df)
        annotations = validate_saved_batch(result, target_df, batch_path)
        atomic_write_json(
            {
                "input_file": input_path.name,
                "batch_number": batch_number,
                "target_start_index": start,
                "target_end_index_exclusive": end,
                "saved_at_utc": utc_now(),
                "annotations": annotations,
            },
            batch_path,
        )
        all_annotations.extend(annotations)

        partial_path = work_dir / f"{input_path.stem}_annotations_partial.csv"
        atomic_write_csv(pd.DataFrame(all_annotations), partial_path)
        LOGGER.info(
            "Batch %d/%d saved (%d rows) in %s.",
            batch_number,
            len(slices),
            len(target_df),
            elapsed_text(time.perf_counter() - batch_start),
        )

    annotations_df = pd.DataFrame(all_annotations)
    expected_ids = df["sentence_id"].astype(str).tolist()
    actual_ids = annotations_df["sentence_id"].astype(str).tolist()
    if actual_ids != expected_ids:
        raise ValueError("Combined annotation checkpoints do not cover the transcript exactly.")
    atomic_write_csv(
        annotations_df, work_dir / f"{input_path.stem}_annotations_complete.csv"
    )
    return annotations_df


def list_to_string(value: Any) -> Any:
    if isinstance(value, list):
        return ", ".join(value)
    return value


def create_final_output(
    input_path: Path,
    output_path: Path,
    df: pd.DataFrame,
    annotations_df: pd.DataFrame,
) -> None:
    columns = [
        "sentence_id", "labels", "error_labels", "repair_labels", "confidence",
        "rationale",
    ]
    final_df = df.merge(annotations_df[columns], on="sentence_id", how="left")
    if final_df["confidence"].isna().any():
        raise ValueError("Final merge contains rows without annotations.")
    for column in ["labels", "error_labels", "repair_labels"]:
        final_df[column] = final_df[column].apply(list_to_string)
    atomic_write_csv(final_df, output_path)
    LOGGER.info("Final annotated output saved: %s", output_path)


def record_failure(work_dir: Path, input_path: Path, exc: Exception) -> None:
    atomic_write_json(
        {
            "input_file": input_path.name,
            "failed_at_utc": utc_now(),
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "resume_note": (
                "Run the script again after fixing the problem. Saved stages and "
                "annotation batches will be skipped automatically."
            ),
        },
        work_dir / "last_failure.json",
    )


def process_one_transcript(client: OpenAI, input_path: Path) -> str:
    transcript_start = time.perf_counter()
    output_path = OUTPUT_DIR / f"{input_path.stem}_annotated.csv"
    work_dir = INTERMEDIATE_DIR / input_path.stem
    work_dir.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not OVERWRITE_COMPLETED:
        LOGGER.info("SKIP completed: %s", output_path.name)
        return "skipped"

    try:
        LOGGER.info("START transcript: %s", input_path.name)
        ensure_compatible_manifest(input_path, work_dir)
        df = load_or_create_processed(input_path, work_dir)
        df = load_or_assign_roles(client, input_path, work_dir, df)
        annotations_df = annotate_with_batch_checkpoints(client, input_path, work_dir, df)
        create_final_output(input_path, output_path, df, annotations_df)
        atomic_write_json(
            {
                "input_file": input_path.name,
                "output_file": output_path.name,
                "completed_at_utc": utc_now(),
                "elapsed_seconds": round(time.perf_counter() - transcript_start, 3),
                "rows": len(df),
            },
            work_dir / "completed.json",
        )
        LOGGER.info(
            "DONE transcript: %s | total time: %s",
            input_path.name,
            elapsed_text(time.perf_counter() - transcript_start),
        )
        return "completed"
    except Exception as exc:
        record_failure(work_dir, input_path, exc)
        LOGGER.exception(
            "FAILED transcript: %s after %s. Saved checkpoints were retained.",
            input_path.name,
            elapsed_text(time.perf_counter() - transcript_start),
        )
        return "failed"


def discover_inputs(start_from: str | None = None) -> list[Path]:
    files = sorted(
        (
            path
            for path in INPUT_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES
        ),
        key=lambda path: path.name.casefold(),
    )
    stems: dict[str, list[str]] = {}
    for path in files:
        stems.setdefault(path.stem.casefold(), []).append(path.name)
    collisions = [names for names in stems.values() if len(names) > 1]
    if collisions:
        raise ValueError(
            "Input files with the same stem would produce the same output name: "
            + "; ".join(", ".join(names) for names in collisions)
        )

    if start_from:
        matching_indices = [
            index
            for index, path in enumerate(files)
            if path.name.casefold() == start_from.casefold()
        ]
        if not matching_indices:
            raise ValueError(
                f"--start-from {start_from!r} was not found in {INPUT_DIR}. "
                "Use the complete filename including its extension."
            )
        files = files[matching_indices[0] :]
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate all CSLA transcripts with safe per-batch resume checkpoints."
    )
    parser.add_argument(
        "--start-from",
        help=(
            "Start the alphabetically sorted run at this exact input filename. "
            "Completed outputs are still skipped unless OVERWRITE_COMPLETED=True."
        ),
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Try later transcripts after one transcript fails.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    configure_logging(INTERMEDIATE_DIR / "batch_annotation.log")
    run_start = time.perf_counter()

    try:
        if not INPUT_DIR.exists():
            raise FileNotFoundError(f"Input folder does not exist: {INPUT_DIR}")
        inputs = discover_inputs(args.start_from)
        if not inputs:
            raise FileNotFoundError(
                f"No supported transcript files were found in {INPUT_DIR}. "
                f"Supported types: {sorted(SUPPORTED_INPUT_SUFFIXES)}"
            )
        client = OpenAI()
    except Exception as exc:
        LOGGER.exception("Cannot start batch run: %s", exc)
        return 1

    LOGGER.info("Found %d transcript(s).", len(inputs))
    counts = {"completed": 0, "skipped": 0, "failed": 0}
    continue_on_error = args.continue_on_error or CONTINUE_AFTER_FILE_ERROR

    for file_number, input_path in enumerate(inputs, start=1):
        LOGGER.info("FILE %d/%d | %s", file_number, len(inputs), input_path.name)
        status = process_one_transcript(client, input_path)
        counts[status] += 1
        if status == "failed" and not continue_on_error:
            LOGGER.info("Stopping after failure. Rerun to resume this transcript.")
            break

    LOGGER.info(
        "RUN SUMMARY | completed=%d skipped=%d failed=%d | elapsed=%s",
        counts["completed"],
        counts["skipped"],
        counts["failed"],
        elapsed_text(time.perf_counter() - run_start),
    )
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
