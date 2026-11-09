"""Licensing configuration for EffSuite."""

import os

# ==============================================================================
# MASTER LICENCE SWITCH
#   False = Licence system disabled (unrestricted / community mode)
#   True  = Licence system active (enforces .efflic licence files)
#
# To re-activate licence enforcement, change False to True below,
# or set the environment variable EFFSUITE_LICENSE_REQUIRED=1.
# ==============================================================================
_ENV_OVERRIDE = os.environ.get("EFFSUITE_LICENSE_REQUIRED")
if _ENV_OVERRIDE is not None:
    LICENSE_REQUIRED = _ENV_OVERRIDE.strip().lower() not in {"0", "false", "no"}
else:
    LICENSE_REQUIRED = False

# Official publisher verification public keys: {key_id: base64_public_key}
PUBLIC_KEYS: dict[str, str] = {
    "2b826ad66827d95e880b7735e90d1ecc": "DdaLIQcrhKk88Q-PV1HcB9xgXsvp0AFwITwLMcTAYdw"
}

PRODUCT_ID = "effsuite"
BUILD_MODE = "community" if not LICENSE_REQUIRED else "production"
