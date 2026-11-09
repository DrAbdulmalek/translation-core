# Medical Translation Preservation Contract

> Status: design contract only. This file does not implement a clinical
> validator and must not be presented as proof that a translation is safe.

## Purpose

The translation engine is a general-purpose component. Medical consumers need
an additional review boundary because a fluent translation can still change a
clinically significant detail.

The following items are high-risk invariants and must be explicitly evaluated
before a translated segment is accepted:

- numeric values, decimal separators, ranges and inequalities;
- units and unit prefixes (for example, mg versus mcg);
- medication names, strengths, routes and frequencies;
- negation and uncertainty (for example, no evidence of versus evidence of);
- laterality and anatomical site;
- dates, durations and temporal relationships;
- allergy status and clinically meaningful positive/negative findings.

## Required behavior

1. Preserve the source text unchanged and store the translation separately.
2. A detected mismatch must produce a review-required result; it must not
   trigger an automatic rewrite or silent correction.
3. A no-mismatch result from a heuristic checker is not proof of clinical
   equivalence and must never be labeled "medically validated".
4. If parsing is uncertain, the result is unknown/review-required, not pass.
5. Keep source/target language, engine, model/version, glossary version and
   relevant processing metadata with the translation record.
6. Do not send patient text to external translation providers by default.
   Remote use must be an explicit, separately authorized operation.
7. Tests must use synthetic examples only. Do not place real patient text,
   identifiers, records or DICOM-derived content in fixtures or CI logs.

## Test matrix required before implementation is promoted

| Invariant | Positive case | Negative/adversarial case |
|---|---|---|
| Numbers | Same number and decimal value in both texts | Missing, changed, duplicated or reordered values |
| Units | Same unit and prefix | mg/mcg, mL/L or other unit substitution |
| Ranges | Same endpoints and comparator | Reversed endpoints or dropped inequality |
| Negation | Semantically equivalent negation | Dropped, inserted or scope-shifted negation |
| Laterality | Equivalent left/right meaning | Left/right swap or omission |
| Medication | Same drug, strength and route | Similar-name substitution or missing strength |
| Uncertainty | Equivalent uncertainty | "possible" converted to definite |
| Dates/durations | Equivalent normalized date/time | Day/month swap or duration change |

## Why simple token matching is insufficient

A source-language token and its target-language equivalent are usually not
identical strings. Negation can be expressed through morphology and scope;
laterality can be implicit or reordered; number formatting varies by locale;
units can be written in multiple forms. Therefore, counting literal words or
checking that a fixed token appears in a test string cannot establish
preservation.

Any future checker must document its supported language pairs and coverage,
return structured findings with evidence spans, and fail closed to
human-review-required when it encounters unsupported forms. It must not claim
to verify clinical meaning.

## Current repository boundary

The current package documents general translation engines, language registry,
quality metrics, translation memory and glossary facilities. This contract
does not assert that a medical-preservation guard currently exists. It is a
specification for a separately reviewed implementation and its tests.
