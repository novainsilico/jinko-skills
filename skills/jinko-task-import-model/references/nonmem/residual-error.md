# Residual error and the uncertainty cone

## What NONMEM says

`$ERROR` relates the prediction to the observation, and `$SIGMA` gives the
variance of the terms in it:

```
Y = F + F*ERR(1) + ERR(2)     combined
Y = F*(1 + ERR(1))            proportional
Y = F*EXP(EPS(1))             exponential
Y = F + ERR(1)                additive
```

The converter recognises all of these however they are spelled, by
differentiating the `Y` expression numerically with respect to each EPS rather
than matching the source text. Diagnostic statements around it — an
`IWRES`, a `SIGMA(i,j)`-weighted `W` — do not disturb the classification.

## What the converted model does

`sigma{Role}` parameters carry the standard deviations, `eps{N}` parameters
carry the draws, and an observed output combines them:

```
cDrugCentralObserved = cDrugCentral * (1 + epsOne) + epsTwo
```

The additive EPS carries the prediction's unit, not `dimensionless`; adding a
dimensionless quantity to a concentration is a dimension error and Jinkō
rejects it.

## The approximation, stated plainly

**NONMEM draws EPS afresh at every observation record. A Jinkō parameter is
constant for a whole simulation.** These are different objects, and no amount
of arrangement makes one into the other.

So `--eps-clones N` expands each patient into N clones that share its
structural parameters and differ only in their EPS draw. Each clone traces a
curve that is consistently scaled relative to the patient's prediction, and the
envelope across clones is the **predictive cone**: how far a whole profile
could plausibly sit from its prediction.

That is a real and useful quantity. It is *not*:

- per-timepoint residual noise, which would need a fresh draw at each
  observation;
- a simulated data set you could re-fit and recover SIGMA from;
- a visual predictive check. A VPC needs per-observation draws.

Use the cone to show plausible spread around individual predictions. Do not
present it as simulated observations.

## Choosing a clone count

The clones sample the residual distribution, so the count sets how well the
envelope is resolved, not how wide it is. 20 gives a readable band and 50 a
smooth one. Cost is multiplicative: 90 patients at 50 clones across 3 arms is
13,500 simulations.
