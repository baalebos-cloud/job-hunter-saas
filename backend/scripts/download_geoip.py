"""Download the MaxMind GeoLite2 City database used for security-event locations.

    MAXMIND_LICENSE_KEY=... python -m backend.scripts.download_geoip

Runs at container start (see backend/Dockerfile) so the licence key never ends
up in an image layer. Skips quietly when no key is set or the file is less than
a week old; never fails the start-up.
"""
import io
import os
import sys
import tarfile
import time
import urllib.request

from backend.app.core.geoip import db_path

URL = ('https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City'
       '&license_key={key}&suffix=tar.gz')
MAX_AGE_SECONDS = 7 * 24 * 3600


def main() -> int:
    key = os.getenv('MAXMIND_LICENSE_KEY', '').strip()
    target = db_path()
    if not key:
        print('geoip: MAXMIND_LICENSE_KEY not set; security events will have no location.')
        return 0
    if os.path.isfile(target) and time.time() - os.path.getmtime(target) < MAX_AGE_SECONDS:
        print('geoip: database is current.')
        return 0
    try:
        with urllib.request.urlopen(URL.format(key=key), timeout=60) as response:
            payload = response.read()
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
            member = next(m for m in archive.getmembers() if m.name.endswith('.mmdb'))
            data = archive.extractfile(member).read()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + '.part'
        with open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, target)
        print(f'geoip: database saved to {target}.')
    except Exception as exc:  # the API must start even if MaxMind is unreachable
        # The URL contains the licence key: never print it or the exception text.
        print(f'geoip: download failed ({type(exc).__name__}); continuing without location.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
