"""What a job's model calls cost, summed across every one of them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UsageTally:
    """One job's running total. A backend records into it; `jobs.py` files the result."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    # Page images are part of the prompt and part of the bill.
    images: int = 0
    image_tokens: int = 0
    # Not every backend reports a price, and a total that silently means "some calls" is
    # worse than no total.
    costed_calls: int = field(default=0, repr=False)
    efforts: set[str] = field(default_factory=set, repr=False)

    def record(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int = 0,
        total_tokens: int | None = None,
        cost_usd: float | None = None,
        effort: str | None = None,
        images: int = 0,
        image_tokens: int = 0,
    ) -> None:
        self.calls += 1
        if effort is not None:
            self.efforts.add(effort)
        self.images += images
        self.image_tokens += image_tokens
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.reasoning_tokens += reasoning_tokens
        self.total_tokens += (
            prompt_tokens + completion_tokens if total_tokens is None else total_tokens
        )
        if cost_usd is not None:
            self.cost_usd += cost_usd
            self.costed_calls += 1

    def provenance(self) -> dict[str, Any] | None:
        """The `generated_from.usage` shape, or nothing when no call was recorded."""
        if not self.calls:
            return None
        usage: dict[str, Any] = {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.reasoning_tokens:
            usage["reasoning_tokens"] = self.reasoning_tokens
        if self.images:
            usage["images"] = self.images
        if self.image_tokens:
            usage["image_tokens"] = self.image_tokens
        if self.costed_calls == self.calls:
            usage["cost_usd"] = round(self.cost_usd, 6)
        if len(self.efforts) == 1:
            usage["reasoning_effort"] = next(iter(self.efforts))
        return usage
