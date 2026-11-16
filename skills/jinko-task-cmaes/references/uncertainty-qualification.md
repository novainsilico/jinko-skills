# Post-calibration uncertainty qualification

An optional check of a completed CMA-ES calibration. It tells which calibrated
parameters the data identify, which compensate each other, and how the
remaining uncertainty propagates to the model outputs. It ports the Jinkō API
cookbooks `post_calibration_uq` and `quantifying_uncertainty`.

Output: a Jinkō document (local mirror `report.md`) with a verdict (PASS, FAIL,
or INCONCLUSIVE), one status per gate, recommended next steps, a slice and a
joint interval per parameter, the parameter correlations, the local
curvature, and plots of slices, parameter pairs, curvature, and prediction
bands.

## Explored range

The result depends on the explored range, so let the user choose it before
the design:

- one factor for all parameters: best / f to best x f (default f = 2);
- ranges per parameter (`--ranges <json>`), for example from biological
  knowledge or the plausible ranges of the model documentation;
- the prior bounds (`--mode prior`).

A factor range is clipped to the prior bounds; a range per parameter is used
as given. A parameter with a non-positive best value needs a range per
parameter or the prior bounds.

## Commands

`scripts/post_calib_uq.py` does the SDK calls, the design, and the maths. Use
it; do not present it to the user as a tool to learn. Use one run directory per
calibration revision, such as `uq/<calibration-sid>-r<revision>/`, unless the
user named one.

1. `best <calibration-sid> --dir <dir> [--revision N | --label L]` reads the
   calibration inputs, priors, and best patient. It refuses a calibration that
   is not completed.
2. `design --dir <dir> [--factor F | --ranges <json> | --mode prior]` writes
   the exploration Vpop: the best patient, 21 slice points per parameter over
   the explored range (dense near the best value), and 512 Sobol patients in
   each of three nested boxes (the explored range, then 1/3 and 1/9 of it
   around the best value).
3. `trial --dir <dir> --folder <folder-id>` prints the plan: patients, arms,
   simulations (patients x arms), and explored ranges. Show it to the user. Run it again with
   `--apply` only after the user agrees. It creates the Vpop and the trial from
   the calibration inputs, and starts the trial.
4. `fetch --dir <dir>` waits for the trial, downloads the scores, and turns
   the model outputs of the near-optimal patients into prediction bands.
5. `analyze --dir <dir>` writes `report.md`, `report.json`, and `plots/`.
6. `publish --dir <dir>` writes `document.md` and previews the Jinkō
   document through the `jinko-document` creation script: the report, its
   plots, and a card for each linked project item. Run it again with
   `--apply --confirm-digest <digest>` to create the document. It goes to the
   folder of the exploration trial unless `--folder` names another one.

Show the verdict, the gate table, the next steps, and the document link.

## Gates

Scores are Jinkō scores: 1 is a perfect fit. A patient is near-optimal when its
weighted score is at most `--delta` (0.05) below the best score.

| Gate | Fails when |
| --- | --- |
| Reproduction | The trial does not reproduce the calibration best score. |
| Simulations | More than 5% of exploration patients fail. |
| Optimum | An explored patient scores more than 0.01 above the best patient. |
| Priors | A best value is more than 3 prior standard deviations from the prior mean. |
| Bounds | A best value sits on a prior bound. |
| Identifiability | A slice (one parameter moves, the others stay at their best value) does not leave the near-optimal region on both sides, or the parameter loads on a weak direction of the fitted curvature together with other parameters (compensated). |
| Correlations | Near-optimal patients show a parameter pair with Spearman \|rho\| >= 0.8, or the local quadratic fit has a flat or positive curvature direction. |

## Rules

- The script writes the recommended next step of each failed gate. Do not
  replace a failed gate with a judgment of your own.
- When the reproduction gate fails, say that the other gates are not
  reliable.
- Change `--delta` only when the user asks; report the value you used.
- Identifiability holds only over the explored range. Say so when you report
  an interval. A slice interval is a lower bound on the uncertainty; report
  the joint interval when there is one.
- Discourage calibrations of more than 10 parameters. The joint check needs a
  number of samples that grows with the square of the dimension, and the
  report then notes that its joint results are unreliable. Recommend
  successive steps of at most 10 parameters.
- Do not edit or relaunch the calibration from this check. A failed gate is a
  recommendation for the user.
