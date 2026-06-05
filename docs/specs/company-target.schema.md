# Company Target Schema

## Owner

The Strategist composition root / cache layer (Phase 5b).

## Consumers

Deterministic source classification (`classify_source` uses the declared domains
to recognise a company's careers pages and engineering blog) and cache keys (the
`name` is the `company_target` key dimension). See axioms 08 and 18.

## Purpose

A target company the user is preparing for, paired with the domains the operator
*explicitly trusts* as its provenance. Domains are declared, never inferred from
the company name — no fuzzy name→domain guessing in the control plane.

## JSON Example

```json
{
  "name": "Stripe",
  "careers_domains": ["stripe.com"],
  "engineering_blog_hosts": ["stripe.com/blog"]
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `name` | Company name; the `company_target` cache-key dimension (non-empty) |
| `careers_domains` | Trusted careers/job-posting domains (default `[]`) |
| `engineering_blog_hosts` | Trusted engineering-blog hosts (default `[]`) |

Domains/hosts are casefolded by `classification_domains` before they reach
`classify_source`.

## Invariants

- `name` is non-empty.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "name": "" }
```

Reason: `name` must be non-empty.

```json
{ "careers_domains": ["stripe.com"] }
```

Reason: `name` is required.

## Related Docs

- `../axioms/08-rag-source-claims.md`
- `../axioms/18-caching-strategy.md`
- `source-claim.schema.md`
