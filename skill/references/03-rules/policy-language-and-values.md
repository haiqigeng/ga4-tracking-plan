# Language And Value Policy

Use this policy before writing event rows or parameter values. The language
decision is part of measurement governance, not a cosmetic workbook choice.

## Language Decision

1. Inspect the client template and brief for an explicit delivery language.
2. Observe the website language selector, locale routes, and market structure.
3. For a multilingual or multi-market website, use English for workbook wording
   and controlled analytics values so reporting remains comparable.
4. For a French-only website, use French workbook wording when it is the most
   useful language for analysts and developers. Controlled semantic values may
   also be French.
5. When website language is unknown, keep `site_languages` unresolved. If the
   user or template explicitly sets a workbook language, use it without
   treating it as website evidence. Keep controlled values in English until
   website or client evidence supports another language. If workbook language
   is also unknown, default the draft workbook to English and disclose the
   unresolved decision.

GA4 event names, official parameter names, custom event names, custom parameter
names, dataLayer keys, and wrapper names always remain English technical names.
Do not translate `view_item`, `item_category`, `page_template`, or equivalent
implementation identifiers.

Record the decision in `language_policy`. A multilingual plan is invalid when
either `workbook_language` or `controlled_value_language` is not `en`.

## Controlled Value Format

For controlled semantic values:

- use lowercase ASCII `snake_case`;
- replace spaces and punctuation with underscores;
- remove accents through deterministic transliteration;
- use one stable value for one meaning across events and markets;
- translate semantic values to the selected controlled-value language before
  normalization;
- display finite values as `value_1 | value_2 | value_3` in the workbook.

For a French controlled-value plan, custom semantic taxonomies must actually be
French after normalization: use `connecte | deconnecte`, `accueil`,
`liste_produits`, `fiche_produit`, `panier`, and `developpement` rather than
`logged_in | logged_out`, `home`, `product_list`, `product_detail`, `cart`, or
`development`. This translation rule does not apply to official enumerations,
ISO values, technical identifiers, or client-confirmed raw system values.

Preserve official ISO codes, currency codes, numbers, booleans, URLs, opaque
product or transaction IDs, and safe dynamic values in their required format.
Do not normalize a raw identifier into a new business value.

## Value Domains And Evidence

Every parameter records one `value_domain`. Finite entries contain the original
website or client label (`raw_label`), the analytics value
(`normalized_value`), source language, mapping method, and `source_ref`.

| Mode | Use |
| --- | --- |
| `observed_exhaustive` | All practical values were observed on the live website. Use for finite sets normally containing 20 values or fewer. |
| `observed_partial` | Representative live values were observed, but the domain is dynamic or too large to exhaust. |
| `client_confirmed` | The client or an authoritative technical artifact supplied the complete values. |
| `official_standard` | Values follow an external standard such as ISO currency or language codes. |
| `proposed_taxonomy` | A transparent analyst proposal awaiting website or client confirmation. Never describe it as observed or exhaustive. |
| `governed_rule` | Values are dynamic or high-cardinality and are governed by a precise rule rather than a list. |
| `not_applicable` | The parameter has no reusable value domain. |
| `blocked` | The value source could not be inspected or confirmed. Do not invent a list. |

Use Playwright or an interactive browser to exhaust visible values such as
filters, sort options, navigation groups, shipping tiers, payment types,
languages, markets, and finite account options. Record page, route, interaction,
or supplied-document references in `source_refs`. An `observed_exhaustive`
parameter must link both its domain and each observed entry to the exact
Playwright, browser-exploration, or synthetic account-exploration reference
recorded in `website_coverage_map`.

Do not attempt to exhaust product IDs, product names, transaction IDs, search
terms, free text, URLs, or similarly dynamic domains. Use `observed_partial` or
`governed_rule` with a concrete format and privacy rule.

A normalized-value list or prose provenance note is not evidence by itself.
Never label values as observed or exhaustive unless the recorded source was
actually inspected.
