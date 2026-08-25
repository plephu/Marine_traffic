"""HTTP client dung chung: retry, gia lap trinh duyet, gioi han toc do, luu raw."""
from __future__ import annotations

import hashlib
import os
import random
import time
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
}


class Fetcher:
    """Boc requests.Session voi retry va tuy chon ghi lai HTML tho de debug."""

    def __init__(self, timeout=30, retries=3, delay=1.0, dump_dir=None, verbose=False):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self.dump_dir = Path(dump_dir) if dump_dir else None
        self.verbose = verbose
        if self.dump_dir:
            self.dump_dir.mkdir(parents=True, exist_ok=True)

    def get(self, url, **kwargs):
        """GET voi retry luy thua; tra ve Response hoac raise requests.RequestException."""
        last = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                self._dump(url, resp.text)
                if self.delay:
                    time.sleep(self.delay + random.uniform(0, 0.4))
                return resp
            except requests.RequestException as exc:
                last = exc
                if attempt == self.retries - 1:
                    break
                time.sleep(2 ** attempt)
        raise last

    def get_text(self, url, **kwargs):
        return self.get(url, **kwargs).text

    def get_json(self, url, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("Accept", "application/json, text/plain, */*")
        return self.get(url, headers=headers, **kwargs).json()

    def _dump(self, url, text):
        if not self.dump_dir:
            return
        digest = hashlib.sha1(url.encode()).hexdigest()[:10]
        safe = "".join(c if c.isalnum() else "_" for c in url[8:80])
        (self.dump_dir / ("%s_%s.html" % (safe, digest))).write_text(text, encoding="utf-8")


def env_key(*names):
    """Lay API key dau tien tim thay trong bien moi truong."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None
