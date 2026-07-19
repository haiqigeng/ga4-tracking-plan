# Fresh-Agent Evaluation

Use this release gate to check that the skill works in a clean conversation,
without relying on prior exchanges or client examples.

## Run Protocol

1. Start a new agent session with only the released skill installed.
2. Run every prompt in `maintenance/evaluations/fresh-agent-evaluation-cases.json` unchanged.
3. Keep generated workbooks, JSON, screenshots, and score files outside the
   repository.
4. Review each required criterion as `pass` or `fail` and each prohibited
   outcome as `absent` or `present`.
5. Record evidence in short human notes. Do not score based only on the final
   prose response; inspect the JSON, XLSX, official source locators, selected
   parameter set, developer examples, and template-fidelity report when the
   case creates them.
6. Validate the result file before release.

The release passes only when every blocking criterion passes, at least 90% of
quality criteria pass, and every prohibited outcome is absent.

## Result Format

```json
{
  "case_results": [
    {
      "case_id": "whole_site_ecommerce",
      "required_outcomes": {
        "journey_coherence": "pass"
      },
      "prohibited_outcomes": {
        "ua_schema": "absent"
      },
      "notes": "Evidence reviewed in the generated JSON and XLSX."
    }
  ]
}
```

Include every criterion from the case manifest. Validate only the manifest
structure with:

```powershell
python scripts/validate_eval_manifest.py
```

Score completed results:

```powershell
python scripts/validate_fresh_agent_evals.py --results path\to\fresh-agent-results.json
```

This is an acceptance test, not a source of client tracking recommendations.
The scenarios are synthetic and use only `example.com` domains.

Repository CI runs the manifest-structure check only and prints that no agent
was executed. It must never be presented as a passing fresh-agent evaluation.
The release gate passes only after the clean sessions were actually run and the
completed results command succeeds.
