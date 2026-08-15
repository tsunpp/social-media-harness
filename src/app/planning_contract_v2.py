def contract_v2() -> str:
    return """Return strict JSON only:
{"reviewer":"string","decision":"PASS | REVISE | HUMAN_REVIEW","recommended_option":"A | B | C | COMBINE | NONE","scores":{"visual_quality":1-10,"authenticity":1-10,"brand_consistency":1-10,"platform_fit":1-10,"risk":1-10},"blocking_issues":[{"id":"string","location":"string","problem":"string","required_change":"string"}],"optional_suggestions":["string"],"summary":"string"}
RISK SCALE IS DIRECTIONAL: risk=1 means no or minimal publication risk; risk=10 means the highest publication risk. It is not a safety or confidence score. PASS requires zero blockers and risk 1-6. Risk 7-10 requires HUMAN_REVIEW with at least one concrete blocker. PASS means the option set is sound enough for owner direction selection; it never selects or authorizes a plan. HUMAN_REVIEW is only for factual/privacy uncertainty or incompatible requirements. Aesthetic preferences are optional suggestions."""

