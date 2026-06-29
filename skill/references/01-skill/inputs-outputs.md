# Inputs And Outputs

Use this file to define what the skill needs and what it should produce.

## Inputs

Required or inferred inputs:

- website URL, page list, sitemap, screenshots, user journey, or written brief;
- website coverage sources, such as sitemap, robots.txt, navigation, URL
  inventory, representative page templates, existing client tracking files, or
  browser/Playwright exploration notes;
- business goal and analysis needs when known;
- expected user actions and success signals;
- existing tracking-plan template, naming convention, or previous GA4/GTM
  documentation when available;
- execution mode signal: client template adaptation, existing plan review,
  event recommendation, or greenfield best-practice plan;
- analytics platform scope: GA4 by default, Piano Analytics only when requested
  or clearly in scope;
- implementation context, such as GTM, dataLayer, gtag.js, CMS, ecommerce
  platform, SPA routing, server-side tagging, or unknown;
- available data, such as page metadata, product data, cart/order data, form
  metadata, user state, and consent state;
- privacy, PII, legal, regional, or technical constraints;
- historical tracking plans only as generic learning material.

If implementation context is unknown, assume standard GTM web container plus
dataLayer and flag the assumption.

## Outputs

Possible outputs:

- human-readable XLSX tracking plan;
- structured JSON plan for validation and future automation;
- long-format CSV for review, diffing, or QA ingestion;
- measurement brief and assumptions;
- execution context, input artifact inventory, and template policy;
- website coverage map for broad website or multi-journey scope;
- measurement strategy and scalability notes;
- journey-grouped Event Matrix;
- Parameter Reference with value rules and examples;
- GTM Protocol;
- Screenshot Register when screenshots or capture requirements are part of the
  planning evidence, generated from event rows and focused on capture
  objectives, automation cues, evidence status, and future recette needs rather
  than local file paths;
- lightweight QA preparation only when useful for handoff to a QA/recette
  skill;
- key event recommendations;
- custom definition recommendations;
- not-tracked decisions;
- documentation sources checked.
- official verification status for events and parameters;
- collection source and duplicate-risk decisions;
- ecommerce parameter profile when ecommerce events are present.

## Default Workbook

The XLSX workbook is the main human deliverable. The Event Matrix should be the
main working tab. Overview, GTM Protocol, Parameter Reference, Screenshot
Register, and QA Cases should support the Event Matrix without becoming dense
or filled with internal reasoning. Do not show internal event IDs, screenshot
IDs, QA IDs, or tracking-row IDs in the Event Matrix; those belong to structured
JSON or the future QA phase if they are needed at all.
