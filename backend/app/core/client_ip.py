"""Client IP resolution that cannot be spoofed with X-Forwarded-For.

``X-Forwarded-For`` is only honoured when the direct peer is a trusted proxy
(the ALB / Railway edge, configured with ``TRUSTED_PROXY_CIDRS``). The chain
is then walked right-to-left, skipping trusted hops, and the first untrusted
address is the client. A header sent by the client itself is ignored.
"""
from __future__ import annotations

import ipaddress
from functools import lru_cache

DEFAULT_TRUSTED = '127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10,fc00::/7'


@lru_cache(maxsize=8)
def _networks(spec: str):
    networks = []
    for part in spec.split(','):
        part = part.strip()
        if part:
            try:
                networks.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                continue
    return tuple(networks)


def _parse(value: str):
    try:
        return ipaddress.ip_address(value.strip().strip('[]').split('%')[0])
    except ValueError:
        return None


def is_trusted(address, spec: str) -> bool:
    ip = _parse(address) if isinstance(address, str) else address
    return ip is not None and any(ip in net for net in _networks(spec))


def resolve_client_ip(peer: str | None, forwarded_for: str | None, trusted_spec: str | None = None) -> str:
    from backend.app.core.config import settings
    spec = trusted_spec if trusted_spec is not None else (settings.TRUSTED_PROXY_CIDRS or DEFAULT_TRUSTED)
    peer = (peer or '').strip()
    if not peer or not is_trusted(peer, spec) or not forwarded_for:
        return peer or 'unknown'
    for hop in reversed([h for h in forwarded_for.split(',') if h.strip()]):
        ip = _parse(hop)
        if ip is None:
            return peer  # malformed chain: do not trust any of it
        if not is_trusted(ip, spec):
            return str(ip)
    return peer


def client_ip(request) -> str:
    peer = request.client.host if request.client else None
    return resolve_client_ip(peer, request.headers.get('x-forwarded-for'))


def mask_ip(address: str) -> str:
    """GDPR-friendly masking: /24 for IPv4, /48 for IPv6."""
    ip = _parse(address or '')
    if ip is None:
        return 'unknown'
    prefix = 24 if ip.version == 4 else 48
    return str(ipaddress.ip_network(f'{ip}/{prefix}', strict=False).network_address) + f'/{prefix}'
