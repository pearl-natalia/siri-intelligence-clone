"""Memory access bound to the verified request owner, never model-supplied IDs."""
import re


class UserMemory:
    def __init__(self, store, user_id, message):
        self.store, self.user_id, self.message = store, user_id, message

    def context(self):
        enabled = self.store.memory_enabled(self.user_id)
        return {"enabled": enabled, "facts": self.store.list_memories(self.user_id) if enabled else []}

    def remember(self, args):
        topic, fact, quote = (args.get(key) for key in ("topic", "fact", "source_quote"))
        if not all(isinstance(value, str) for value in (topic, fact, quote)):
            return {"success": False, "message": "A topic, fact and exact user quote are required."}
        topic = re.sub(r"\s+", " ", topic).strip().casefold()
        fact = re.sub(r"\s+", " ", fact).strip()
        if not 1 <= len(topic) <= 80 or not 1 <= len(fact) <= 500 or len(quote.strip()) < 3 or quote not in self.message:
            return {"success": False, "message": "Save only a short fact supported by an exact quote in the current user message."}
        return self.store.remember(self.user_id, topic, fact)

    def forget(self, args):
        fact_id, quote = args.get("id"), args.get("source_quote")
        if not isinstance(fact_id, str) or not isinstance(quote, str) or len(quote.strip()) < 3 or quote not in self.message:
            return {"success": False, "message": "An explicit request in the current message is needed to forget a fact."}
        from werkzeug.exceptions import NotFound
        try:
            self.store.forget(self.user_id, fact_id)
        except NotFound:
            return {"success": False, "message": "That memory is unavailable in this account."}
        return {"success": True, "message": "The saved fact was removed. Its original chat may still contain it."}
