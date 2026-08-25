"""Du lieu mau cho che do demo: dung khi khong co mang de thu giao dien.

Sinh HTML dang bang giong trang cang vu that, voi ETA tinh theo thoi diem hien tai
nen luon roi vao cua so dang xem. Mot so tau co mat o nhieu 'nguon' de thay ro
co che gop trung.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from .dates import now_vn

# Tau xuat hien o nhieu nguon (de minh hoa gop trung) - (ten, imo, quoc tich, GT)
SHARED_FLEET = [
    ("MAERSK NEWPORT", "9525663", "SINGAPORE", 25145),
    ("SITC HAIPHONG", "9612777", "MARSHALL IS.", 9528),
    ("EVER LOTUS", "9604693", "PANAMA", 67170),
]

LOCAL_FLEET = [
    ("HAI NAM 68", "9188219", "VIET NAM", 2989),
    ("TAN CANG PIONEER", "9433781", "VIET NAM", 8240),
    ("NORD SUPERIOR", "9721057", "SINGAPORE", 43000),
    ("GAS ARIES", "9366473", "MARSHALL IS.", 5200),
    ("PHUC HUNG 09", "9410313", "VIET NAM", 3120),
    ("BIENDONG NAVIGATOR", "9312284", "VIET NAM", 11200),
]

BERTHS = ["Cau so 1", "Cau so 2", "Cau so 3", "Cau Chua Ve", "Cau Dinh Vu", "Phao so 5"]
AGENTS = ["VOSA", "MAERSK VIET NAM", "SITC VIET NAM", "GEMADEPT", "VIETFRACHT"]
FROM_PORTS = ["SINGAPORE", "HONG KONG", "BUSAN", "SHANGHAI", "PORT KLANG", "KAOHSIUNG"]


def _seed(url):
    return int(hashlib.sha1(url.encode()).hexdigest()[:8], 16)


def demo_html(url, rows=8):
    """Sinh mot bang HTML mau cho URL bat ky."""
    seed = _seed(url)
    now = now_vn()
    fleet = SHARED_FLEET + [LOCAL_FLEET[(seed + i) % len(LOCAL_FLEET)] for i in range(rows)]

    lines = [
        "<html><body><h2>DU LIEU DEMO - %s</h2>" % url,
        "<table>",
        "<tr><th>TT</th><th>Ten tau</th><th>IMO</th><th>Quoc tich</th><th>GT</th>"
        "<th>Thoi gian den</th><th>Cau ben</th><th>Den tu</th><th>Dai ly</th></tr>",
    ]
    for index, (name, imo, flag, gt) in enumerate(fleet[:rows]):
        # ETA trai deu trong 0-28 ngay toi; tau dung chung lech vai gio giua cac nguon
        offset_hours = ((seed >> (index % 12)) % 28) * 24 + (seed + index * 7) % 20
        eta = now + timedelta(hours=offset_hours + 6)
        lines.append(
            "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td>"
            "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                index + 1, name, imo, flag, gt,
                eta.strftime("%d/%m/%Y %H:%M"),
                BERTHS[(seed + index) % len(BERTHS)],
                FROM_PORTS[(seed + index * 3) % len(FROM_PORTS)],
                AGENTS[(seed + index * 5) % len(AGENTS)]))
    lines.append("</table></body></html>")
    return "\n".join(lines)


class DemoFetcher:
    """Thay the Fetcher: khong goi mang, tra ve bang mau cho moi URL."""

    def __init__(self, *args, **kwargs):
        self.calls = []

    def get_text(self, url, **kwargs):
        self.calls.append(url)
        return demo_html(url)

    def get_json(self, url, **kwargs):
        raise RuntimeError("che do demo khong mo phong nguon API")
