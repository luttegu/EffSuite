"""Offline cryptographic license management for EffSuite.

Uses Ed25519 digital signatures to verify offline customer licenses.
Independent of numerical physics engines.
"""
from .verification import License, LicenseError, verify_license
from .storage import LicenseStore, default_store
from .config import LICENSE_REQUIRED, PUBLIC_KEYS, PRODUCT_ID, BUILD_MODE

__all__ = [
    "License",
    "LicenseError",
    "verify_license",
    "LicenseStore",
    "default_store",
    "LICENSE_REQUIRED",
    "PUBLIC_KEYS",
    "PRODUCT_ID",
    "BUILD_MODE",
]
