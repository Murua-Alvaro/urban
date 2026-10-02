# Validation gate

Validation is a hard gate between loading and cleaning. The validator checks the eight-field aggregated schema, municipality references, duplicate grouped keys, non-negative integer weights, declared totals, SCIAN formats, contact-flag range and geography quality indicators.

Postal-code plausibility is deliberately recorded as a warning/quality metric rather than silently deleting rows. Provisional AGEB codes are preserved. Cleaning must not alter the raw extraction.
