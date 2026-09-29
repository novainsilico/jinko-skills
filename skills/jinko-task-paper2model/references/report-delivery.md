# Report delivery

The renderer builds the layout, checks card URLs against recorded SIDs, refuses
a bare SID anywhere in the output, and binds visual evidence to measured
targets. Use it rather than rebuilding any of that by hand.

## Report shape

Title, then created artifact cards, then source Reference cards, each an
unversioned SDK `.url` alone in a paragraph. Findings next: outcome, confidence,
key agreement or failure, and scope, with every required target's status and its
predeclared metric and tolerance. Evidence matrices and binding tables stay in
the local audit; give its path in the delivery note, or say it is pending.
Separate publication fidelity from curated implementation
agreement. Summarize active decisions with their defense. Keep superseded
decisions clearly labeled in audit history. For reporting transformations,
show raw and transformed comparisons and retain their selection dependencies.

Use the supplied paper title, or the generic "Reproduction report". Never derive
a title from a SID. Take the host from `JINKO_URL`, preferably through the
resource's `.url`, and never guess one. Revision links use
`url_with_fixed_revision(...)` with normal Markdown labels.

Without tools, reproduce the layout directly: one title, then supplied card URLs,
then findings. With no receipts, findings start after the title. Omit empty
sections.

## Claims that must come from evidence

Never infer target independence, absence of source conflicts, completed hashes,
or absence of biological variability from a reviewed source or a missing band.

Preserve inherited target independence unless recorded selection evidence makes
the target non-independent; document that change. A better result or a new
decision ID cannot restore independence. With
no supplied value write `unknown` or omit the label, and say **required target**
everywhere else. Unknown in a handoff does not mean absent in the stored
specification, so never clear its Boolean.

Copy `solve_status` from the execution receipt into every section. A failed
comparison can follow a passed solve and is not a failed solve. For one, this
rationale is sufficient: "The model executes, but the required target fails its
declared tolerance." A solve or an RMSE value alone never establishes
qualitative reproduction, so check the report for unsupported uses of
"independent" and "qualitatively reproduced" before delivery.

## Visual evidence

Plot publication data and actual results on matching axes with units, arm and row
identity, and source locators, showing the predeclared metric and tolerance.
Include failed comparisons and missing curve segments. Describe reported
variability and digitization uncertainty separately, and state when either is
unavailable. Never infer a confidence band from deterministic points.

Embed with `![caption](path)`; a bullet holding the path does not display it.
Record image and comparison data in `artifacts` with hashes. The renderer embeds
what you supply and does not check its science, so review it against retained
data. If plotting fails, say why in `limitations` and keep the metrics. Omit
image records for blocked work. Upload through `jinko-document`, which validates
local paths; never invent a hosted image URL.

## Renderer commands

```bash
python scripts/paper2model_report.py render --spec reproduction-spec.json \
  --profile audit --out reproduction-audit.md
python scripts/paper2model_report.py render --spec reproduction-spec.json \
  --profile jinko --out reproduction-report.md
python -m jinko.cli.create_document_from_markdown \
  --name "Paper reproduction" --markdown-file reproduction-report.md \
  --output-markdown reproduction-report.upload.md
```

The document command previews only: no images uploaded, no hosted URLs returned.
Repeat with `--apply --confirm-digest <preview-digest>` after review.

## Blocked reports

Use only: title, outcome and confidence, one sentence on the access gap, the
frozen unavailable target, and the source request. State that visuals are
unavailable. Keep schema and pending-operation detail in the local note.

Preserve access results literally: a denial stays `inaccessible`, not
`not_found`. Given only a combined failure, repeat that fact without inventing
routes, URLs, dates, or hashes.

## Source access request

After reasonable publisher, repository, and linked-source attempts fail, ask:

> I could not retrieve [exact title, DOI, and supplement filename or primary
> paper]. I tried [URLs and access results]. It is needed for [equation, table,
> parameter, or target]. Do you have access and can you upload it or provide an
> accessible link? I will continue with [independent sources] meanwhile.
> Access status: `awaiting_user_source`.

Add an `awaiting_user_source` retrieval record with the known URL, the requested
source in `purpose`, empty `source_ids`, and the request and affected work in
`note`. With no known URL, record the request in `limitations` until one exists.
This is an access state, not a scientific outcome: `blocked_evidence` stays
reserved for a blocked implementation.
