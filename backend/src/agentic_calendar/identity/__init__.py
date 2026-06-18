"""Per-user Google identity + credential persistence (hosted frontend).

A leaf region (like ``consent``): it owns the mapping from a Google account
(stable ``sub``) to the app ``user_id``, the user's encrypted OAuth token, and
their dedicated secondary calendar id. It depends only on ``common`` and
``contracts`` and is imported only by the composition root (``app/``) — never
by another region.

The token stored here is *ciphertext*: encryption is the caller's job (see
:class:`agentic_calendar.common.secrets.TokenCipher`), so this store stays a
dumb, crypto-oblivious persistence layer with an in-memory twin for tests.
"""
