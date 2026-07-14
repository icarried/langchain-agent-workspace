"""Reusable, namespace-isolated knowledge base services."""

from .manager import KnowledgeBaseManager
from .settings import KnowledgeBaseSettings

__all__ = ["KnowledgeBaseManager", "KnowledgeBaseSettings"]
