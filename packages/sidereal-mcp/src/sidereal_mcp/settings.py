from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ADDR_VAR = "SIDEREAL_MCP_ADDR"
DEFAULT_ADDR = "127.0.0.1:50053"


@dataclass(frozen=True, slots=True)
class Address:
    host: str
    port: int


def serves_http(env: Mapping[str, str] | None = None) -> bool:
    """HTTP is opt-in: setting the address turns it on, as `--http` does."""
    source = os.environ if env is None else env
    return bool(source.get(ADDR_VAR))


def mcp_address(env: Mapping[str, str] | None = None) -> Address:
    source = os.environ if env is None else env
    addr = source.get(ADDR_VAR) or DEFAULT_ADDR
    host, _, port = addr.rpartition(":")
    if not host or not port.isdigit():
        raise ValueError(f"{ADDR_VAR} must be host:port, not {addr!r}")
    return Address(host=host, port=int(port))
