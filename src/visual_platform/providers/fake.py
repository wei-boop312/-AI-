class FakeProvider:
    """No network transport; unknown submission is deliberately never retried."""
    def __init__(self): self.calls = {}; self.results = {}
    def submit(self, intent_id, mode="success"):
        if intent_id in self.calls: raise RuntimeError("submission already attempted")
        if mode not in ("success", "failed", "uncertain", "late"): raise ValueError("unknown mode")
        self.calls[intent_id] = 1
        self.results[intent_id] = mode
        return {"status":mode,"provider_id":intent_id if mode in ("success","late") else None}
    def poll(self, provider_id):
        state=self.results[provider_id]
        return "succeeded" if state in ("success","late") else state
