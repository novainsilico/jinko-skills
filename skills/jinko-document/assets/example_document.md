# Example Jinkō Document

## Executive Summary

This markdown file is a starter for Jinkō document creation through the SDK.

## Embedded Project Items

Put each Jinkō project-item URL on its own paragraph when you want a card render:

https://configured-jinko.example/cm-EXAMPLE-1234

https://configured-jinko.example/so-EXAMPLE-1234

## Table

| Quantity | Value | Unit |
| --- | ---: | --- |
| Clearance | 12.4 | L/h |
| Volume | 46.0 | L |

## Equation

Use single dollar signs for an inline mathematical expression: $C(t) = \frac{\mathrm{Dose}}{V} e^{-\frac{CL}{V}t}$.

Use a `mathBlock` fenced code block for a display mathematical expression:

```mathBlock
\frac{dC}{dt} = k_{\mathrm{in}} - k_{\mathrm{out}} C
```

## Images

Local image paths are rewritten by the bundled script:

![Example local image](./example-image.jpg)

## References

In-text citations such as [1] and [2] stay in the text. Link bibliography
entries to their existing Jinkō Reference URLs.
