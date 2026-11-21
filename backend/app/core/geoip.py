"""Offline IP geolocation with a MaxMind GeoLite2 City database.

The lookup runs locally, so visitor IPs are never sent to a third-party
service. Set GEOIP_DB_PATH to the .mmdb file (scripts/download_geoip.py fetches
it with a free MAXMIND_LICENSE_KEY). Without the file, lookups return an empty
location and nothing else changes.
"""
from __future__ import annotations

import ipaddress
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)
DEFAULT_DB_PATH = '/tmp/geoip/GeoLite2-City.mmdb'
EMPTY = {'country_code': None, 'country': None, 'region': None, 'city': None}


def db_path() -> str:
    return os.getenv('GEOIP_DB_PATH', DEFAULT_DB_PATH)


@lru_cache(maxsize=1)
def _reader():
    path = db_path()
    if not os.path.isfile(path):
        return None
    try:
        import geoip2.database
        return geoip2.database.Reader(path)
    except Exception as exc:  # unreadable or corrupt database: run without geolocation
        logger.warning('geoip_unavailable error_type=%s', type(exc).__name__)
        return None


def locate(address: str | None) -> dict:
    """{country_code, country, region, city} for a public IP; private ranges are labelled."""
    try:
        ip = ipaddress.ip_address((address or '').strip())
    except ValueError:
        return dict(EMPTY)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return {**EMPTY, 'country': 'Private network'}
    reader = _reader()
    if reader is None:
        return dict(EMPTY)
    try:
        r = reader.city(str(ip))
    except Exception:  # address not in the database
        return dict(EMPTY)
    region = r.subdivisions.most_specific.name if r.subdivisions else None
    return {'country_code': r.country.iso_code, 'country': r.country.name, 'region': region, 'city': r.city.name}


def available() -> bool:
    return _reader() is not None
