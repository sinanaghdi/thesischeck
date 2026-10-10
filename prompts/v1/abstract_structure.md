# Abstract structure analysis — v1

Return JSON only, matching the supplied schema. Analyze only the provided abstract text and its document evidence. Do not rewrite the abstract or invent claims.

Assess whether the text explicitly covers: problem/context, objective, method, principal result, and conclusion. Treat missing evidence as unknown, not proof of absence. Every finding must include an exact quotation from the supplied text, stable element ID, and a confidence between 0 and 1. Do not generate citations, metrics, or results.
