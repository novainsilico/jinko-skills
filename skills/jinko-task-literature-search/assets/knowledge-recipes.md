# Knowledge Search Recipe

Use Knowledge searches for orientation on a disease, mechanism, treatment,
population, or clinical paradigm. Prefer reviews and guidelines for broad
questions; loosen publication type and date constraints for landmark evidence.

## Angles

Build at least three distinct angles from the shared Entity Table:

- indexed topic: `<ENTITY>[mh] AND Review[pt]`;
- title/abstract mechanism: `<ENTITY>[tiab] AND (pathophysiology[tiab] OR mechanisms[tiab])`;
- related entity: `<ENTITY>[tiab] AND <RELATED_ENTITY>[tiab]`;
- optional venue or guideline angle using `[ta]` or `Practice Guideline[pt]`.

Use `humans[mh]` for human-scale questions; omit it for basic biology. Default to
recent reviews unless historical coverage was requested.

## Priority

Prioritize candidates supported by at least two of these signals:

- returned by multiple angles;
- title indicates a review, primer, pathogenesis, mechanism, guideline, or
  state-of-the-art overview;
- authoritative review venue;
- strong age-adjusted citation evidence.

One signal is medium priority; none is low. Retain complementary high-quality
reviews rather than collapsing them solely because their topics overlap.
