"""Reuse the existing immutable evidence I/O helpers."""
from integration.jev27b.storage import canonical, digest, file_hash, read, write

__all__ = ['canonical', 'digest', 'file_hash', 'read', 'write']
