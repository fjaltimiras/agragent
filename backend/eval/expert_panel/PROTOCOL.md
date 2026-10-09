# Expert-panel validation of recommendation quality — protocol

This is the instrument for the evaluation the manuscript declares as future work. It is **not** executed:
no ratings exist yet, and none may be simulated. Tool-selection accuracy (the 63-query benchmark) measures
whether the assistant calls the right function; this protocol measures whether the resulting **advice** is
agronomically sound, which is a different and unmeasured question.

## What is rated

The free-text answer (`final_text`) the assistant produced for each benchmark query, taken verbatim from
`eval/results_<provider>_<model>.json`. Raters see the query and the answer. They do **not** see which tools
were called, the model name, or any other rater's scores.

## Panel

Minimum 3 independent agronomists with viticulture experience, none an author of the manuscript. If raters
work at the same institution as an author, record it: it must be disclosed in the reported results.

## Sampling

All 55 on-topic queries, or a stratified random sample of at least 36 (3 per on-topic category) if rater time
is limited. The 8 out-of-scope queries are excluded: abstention is already measured objectively and there is
no advice to judge. Record the sampling decision in `panel_config.json` so the reported N is auditable.

## Instrument

Each answer is rated on four 5-point Likert items (1 = strongly disagree, 5 = strongly agree):

| Item | Statement |
|---|---|
| `factual` | The agronomic facts stated in the answer are correct. |
| `complete` | The answer addresses what was asked, without material omissions. |
| `safe` | Following this answer would not risk agronomic or economic harm. |
| `grounded` | The answer stays within what the stated data support and does not overclaim. |

Plus one binary flag and one free-text field:

- `hallucination` (yes/no): the answer asserts a specific fact, figure, or citation that is fabricated.
- `comment`: required whenever `safe <= 2` or `hallucination = yes`.

**A `safe` score of 1 or 2 is a blocking finding**, not an average to be diluted: report those cases
individually, since an incorrect irrigation or fertilizer recommendation has direct economic consequences.

## Scoring

`score_panel.py` reports, per item: mean, standard deviation, and the proportion of ratings >= 4. Inter-rater
agreement is Fleiss' kappa over the ordinal items collapsed to agree (4-5) / neutral (3) / disagree (1-2), and
Cohen's kappa on the binary hallucination flag for the 2-rater case. Report kappa **with** its interpretation
band and never in isolation from the raw distribution.

Do not report a single composite "quality score". The four items answer different questions and the manuscript's
claim is specifically about factuality, completeness, safety, and groundedness separately.

## Reporting

Whatever the outcome, it replaces the Limitations sentence stating that these metrics "remain unmeasured", and
the corresponding Future Work item. If the panel finds material problems, that is a publishable result and must
be reported as such rather than softened: the manuscript's current position is that the architecture is viable
and the advice quality is unknown.

## Workflow

```
python3 build_panel_workbook.py --results ../results_cerebras_zai-glm-47.json --raters 3 --sample 36
#   -> panel_workbook_rater{1,2,3}.csv   (blind, shuffled, one row per answer)
#   -> panel_config.json                 (sampling + seed, for auditability)
# ... raters fill in the score columns ...
python3 score_panel.py panel_workbook_rater*.csv
```
