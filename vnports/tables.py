"""Trich bang HTML thanh danh sach dict, tu dong nhan dien cot theo tu khoa.

Cac trang cang vu / terminal Viet Nam doi markup thuong xuyen, nen thay vi
gan chet CSS selector, module nay do tim moi <table>, doc hang tieu de va
anh xa tieu de sang truong chuan bang bo tu khoa (Viet + Anh).
"""
from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

# Tu khoa nhan dien cot -> ten truong chuan. Kiem tra theo thu tu nay,
# cot dac hieu (imo, mmsi) dat truoc cot chung chung (ten, gio).
COLUMN_KEYWORDS = [
    ("imo", ("imo",)),
    ("mmsi", ("mmsi",)),
    ("call_sign", ("callsign", "call sign", "hohieu", "ho hieu", "hô hiệu")),
    ("eta", ("eta", "dukiendn", "du kien den", "thoi gian den", "gio den", "ngay den",
             "arrival", "den cang", "thoigianden", "dendk")),
    ("etd", ("etd", "du kien roi", "gio roi", "ngay roi", "departure", "roi cang")),
    ("vessel_name", ("ten tau", "tau", "vessel", "ship name", "ship", "name")),
    ("flag", ("quoc tich", "flag", "co tau")),
    ("vessel_type", ("loai tau", "type", "kieu tau")),
    ("gross_tonnage", ("gt", "grt", "dung tich", "gross")),
    ("dwt", ("dwt", "trong tai")),
    ("loa", ("loa", "chieu dai", "length")),
    ("from_port", ("tu cang", "cang di", "from", "last port", "cang truoc", "den tu")),
    ("berth", ("cau", "ben", "berth", "vi tri", "cau ben")),
    ("terminal", ("terminal", "cang", "khu vuc", "port")),
    ("agent", ("dai ly", "agent", "chu tau")),
    ("voyage", ("chuyen", "voyage", "voy")),
    ("cargo", ("hang hoa", "cargo", "loai hang")),
]


def strip_accents(text):
    """Bo dau tieng Viet de so khop tieu de cot khong phu thuoc dau."""
    nfkd = unicodedata.normalize("NFD", str(text))
    out = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return out.replace("đ", "d").replace("Đ", "D")


def _norm_header(text):
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def map_header(header):
    """Anh xa mot o tieu de sang ten truong chuan, hoac None neu khong khop."""
    h = _norm_header(header)
    if not h:
        return None
    for field_name, keywords in COLUMN_KEYWORDS:
        for kw in keywords:
            k = _norm_header(kw)
            if h == k or re.search(r"\b" + re.escape(k) + r"\b", h) or k in h.replace(" ", ""):
                return field_name
    return None


def _cell_text(cell):
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def extract_tables(html, min_rows=1, min_cols=2):
    """Tra ve danh sach bang; moi bang la list cac dict {truong_chuan|colN: gia tri}.

    Bang khong co <th> se dung hang dau tien lam tieu de neu hang do khop
    duoc it nhat mot tu khoa; nguoc lai cac cot duoc dat ten col0, col1, ...
    """
    soup = BeautifulSoup(html, "lxml")
    tables = []
    for table in soup.find_all("table"):
        rows = [tr.find_all(["td", "th"]) for tr in table.find_all("tr")]
        rows = [r for r in rows if r]
        if len(rows) < min_rows + 1:
            continue

        header_cells = [_cell_text(c) for c in rows[0]]
        mapped = [map_header(h) for h in header_cells]
        header_row_used = 1
        if not any(mapped) and len(rows) > 1:
            alt = [map_header(_cell_text(c)) for c in rows[1]]
            if any(alt):  # tieu de nam o hang thu hai (bang co hang gop)
                header_cells, mapped, header_row_used = [_cell_text(c) for c in rows[1]], alt, 2
        if not any(mapped):
            continue

        names, seen = [], {}
        for idx, name in enumerate(mapped):
            name = name or ("col%d" % idx)
            if name in seen:  # cot trung ten -> them hau to
                seen[name] += 1
                name = "%s_%d" % (name, seen[name])
            else:
                seen[name] = 0
            names.append(name)

        records = []
        for cells in rows[header_row_used:]:
            if len(cells) < min_cols:
                continue
            values = [_cell_text(c) for c in cells]
            if not any(values):
                continue
            rec = {"_raw_header": header_cells}
            for idx, value in enumerate(values):
                rec[names[idx] if idx < len(names) else "col%d" % idx] = value
            records.append(rec)
        if records:
            tables.append(records)
    return tables


def best_table(html, required=("vessel_name",)):
    """Chon bang co nhieu hang nhat va chua du cac truong bat buoc."""
    candidates = []
    for records in extract_tables(html):
        keys = set().union(*(set(r) for r in records))
        if all(req in keys for req in required):
            candidates.append(records)
    return max(candidates, key=len) if candidates else []
