def evaluate(final_sha256, targets, *, evidence_verified=False, analysis_complete=False, hard_failures=()):
    if len(final_sha256)!=64 or any(c not in "0123456789abcdef" for c in final_sha256):
        raise ValueError("invalid final hash")
    # Verified rule-set completeness has not been implemented. Never auto-pass.
    results=[]
    for target in targets:
        reasons=list(hard_failures)
        if not evidence_verified: reasons.append("rule_evidence_unverified")
        if not analysis_complete: reasons.append("analysis_incomplete")
        if not reasons: reasons.append("complete_verified_rule_set_not_implemented")
        results.append({"platform":target,"status":"non_compliant" if hard_failures else "manual_review","reasons":reasons})
    return {"final_sha256":final_sha256,"per_platform":results}
