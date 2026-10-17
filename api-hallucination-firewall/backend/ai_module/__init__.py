"""Gemma 4 explanation layer for API Hallucination Firewall."""

from .explain import generate_explanation
from .gemma_client import AIUnavailableError, GemmaClient
from .schemas import ExplanationResult, Finding

__all__ = ["generate_explanation", "ExplanationResult", "Finding", "GemmaClient", "AIUnavailableError"]
