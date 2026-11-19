"""Validation for user-supplied URLs that are stored and later shown/followed.

Only https:// URLs to public hosts are accepted: no credentials, no IP
literals in private/loopback/link-local/reserved ranges, no internal names,
and hostnames that currently resolve to non-public addresses are rejected
(SSRF defence for any future server-side fetch).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048
BLOCKED_SUFFIXES = ('.local', '.localhost', '.internal', '.intranet', '.lan', '.home', '.corp', '.railway.internal')


class UnsafeUrl(ValueError):
    pass


def _is_public(ip) -> bool:
    return ip.is_global and not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                                 or ip.is_reserved or ip.is_unspecified)


def validate_public_https_url(value: str, *, resolve: bool = True) -> str:
    url = (value or '').strip()
    if not url or len(url) > MAX_URL_LENGTH or any(ord(c) < 33 for c in url):
        raise UnsafeUrl('Provide a valid https:// link.')
    parts = urlsplit(url)
    if parts.scheme.lower() != 'https':
        raise UnsafeUrl('Only https:// links are allowed.')
    if parts.username or parts.password or '@' in parts.netloc:
        raise UnsafeUrl('Links must not contain credentials.')
    host = (parts.hostname or '').rstrip('.').lower()
    if not host or host == 'localhost' or host.endswith(BLOCKED_SUFFIXES) or '.' not in host and ':' not in host:
        raise UnsafeUrl('Link to a public website.')
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrl('Provide a valid https:// link.') from exc
    if port not in (None, 443):
        raise UnsafeUrl('Links must use the standard https port.')
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public(literal):
            raise UnsafeUrl('Link to a public website.')
    elif resolve:
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError, OSError):
            raise UnsafeUrl('This link could not be resolved.')
        if any(not _is_public(ipaddress.ip_address(info[4][0].split('%')[0])) for info in infos):
            raise UnsafeUrl('Link to a public website.')
    return url
