"""Danh muc day du cac nguon co the lay 'tau du kien cap cang Viet Nam'.

Ba nhom, khac nhau ve tam nhin ETA:
  * ais           : theo doi AIS (VesselFinder, MyShipTracking, MarineTraffic...)
                    -> chinh xac nhung chi thay tau da khai bao hanh trinh, ~1-7 ngay.
  * port_authority: ke hoach dieu dong tau cua Cang vu hang hai (chinh thuc)
                    -> day du nhat cho vung nuoc do, nhung chi 1-3 ngay toi.
  * terminal      : lich cau ben cua tung cang/terminal -> ~7-14 ngay.
  * carrier       : lich tau cua hang tau -> 14-45 ngay, phu ho tam nhin 30 ngay.

`verified=False` nghia la duong dan/cau truc bang chua duoc doi chieu voi trang
that (moi truong dung de viet code nay bi chan egress). Chay `vnports doctor`
tren may co mang de xac nhan truoc khi dua vao san xuat.
"""
from __future__ import annotations

from .apis import build_api_sources
from .base import HtmlTableSource


def _ais_web():
    return [
        HtmlTableSource(
            name="vesselfinder_expected",
            kind="ais",
            url_template="https://www.vesselfinder.com/ports/{vf_id}/expected-arrivals",
            homepage="https://www.vesselfinder.com/ports/VNSGN001",
            coverage="Tau du kien den cang (mien phi, gioi han so hang hien thi).",
            horizon_days=7,
            id_field="vesselfinder_id",
        ),
        HtmlTableSource(
            name="vesselfinder_port",
            kind="ais",
            url_template="https://www.vesselfinder.com/ports/{vf_id}",
            homepage="https://www.vesselfinder.com/",
            coverage="Trang tong hop cang: den/di gan day + tau du kien.",
            horizon_days=7,
            id_field="vesselfinder_id",
        ),
        HtmlTableSource(
            name="myshiptracking_port",
            kind="ais",
            url_template="https://www.myshiptracking.com/ports-arrivals-departures/?pid={mst_id}",
            homepage="https://www.myshiptracking.com/ports/port-of-hai-phong-in-vn-vietnam-id-4079",
            coverage="Estimated arrivals theo cang; ID cang lay tu URL trang cang.",
            horizon_days=5,
            id_field="myshiptracking_id",
        ),
        HtmlTableSource(
            name="marinetraffic_port_web",
            kind="ais",
            url_template="https://www.marinetraffic.com/en/ais/details/ports/{mt_id}",
            homepage="https://www.marinetraffic.com/",
            coverage=("Trang cang MarineTraffic. Thuong bi Cloudflare chan bot - "
                      "uu tien dung marinetraffic_api."),
            horizon_days=7,
            id_field="marinetraffic_id",
        ),
        HtmlTableSource(
            name="alltrack_portcalls",
            kind="ais",
            url_template="https://alltrack.org/list-port-of-calls-{mt_id}-{unlocode}-ho-chi-minh",
            homepage="https://alltrack.org/",
            coverage="Danh sach port call mien phi, doi chieu cheo voi cac nguon AIS khac.",
            horizon_days=5,
            id_field="marinetraffic_id",
        ),
    ]


# Ke hoach dieu dong tau cua cac Cang vu hang hai - nguon chinh thuc, mien phi.
# Nhieu trang co tham so do lech ngay ({d}) de xem ke hoach ngay mai/ngay kia.
def _port_authorities():
    configs = [
        ("cvhh_haiphong", "Hai Phong", "haiphong",
         "https://csdltau.cangvuhaiphong.gov.vn/pages/ship_plan.aspx?d={d}",
         [0, 1, 2, 3], "https://cangvuhaiphong.gov.vn/ke-hoach-tau/"),
        ("cvhh_vungtau", "Vung Tau - Cai Mep", "vungtau",
         "https://cangvuhanghaivungtau.gov.vn/Index.aspx?page=khddt&d={d}",
         [0, 1, 2, 3], "https://cangvuhanghaivungtau.gov.vn/"),
        ("cvhh_hcm", "TP Ho Chi Minh", "hochiminh",
         "http://cangvuhanghaitphcm.gov.vn/index.aspx?cat=2033&page=shipschedule",
         [0], "http://cangvuhanghaitphcm.gov.vn/"),
        ("cvhh_danang", "Da Nang", "danang",
         "https://cangvuhanghaidanang.gov.vn/vi/ke-hoach-dieu-dong-tau-thuyen",
         [0], "https://cangvuhanghaidanang.gov.vn/"),
        ("cvhh_nhatrang", "Nha Trang - Van Phong", "nhatrang",
         "https://cangvuhanghainhatrang.gov.vn/showtv/",
         [0], "https://cangvuhanghainhatrang.gov.vn/"),
        ("cvhh_quangninh", "Quang Ninh", "quangninh",
         "https://kht1.cangvuhanghaiquangninh.gov.vn/vitritau.aspx",
         [0], "https://cangvuhanghaiquangninh.gov.vn/"),
        ("cvhh_nghean", "Nghe An - Cua Lo", "nghean",
         "https://cangvuhanghainghean.gov.vn/",
         [0], "https://cangvuhanghainghean.gov.vn/"),
        ("cvhh_cantho", "Can Tho", "cantho",
         "https://cangvuhanghaicantho.gov.vn/",
         [0], "https://cangvuhanghaicantho.gov.vn/"),
    ]
    sources = []
    for name, label, port_key, url, offsets, home in configs:
        sources.append(HtmlTableSource(
            name=name,
            kind="port_authority",
            url_template=url,
            homepage=home,
            coverage="Ke hoach dieu dong tau - Cang vu hang hai %s (chinh thuc, mien phi)." % label,
            horizon_days=max(offsets) if offsets else 0,
            day_offsets=offsets,
            global_source=True,
            port_key=port_key,
        ))
    return sources


def _terminals():
    configs = [
        ("eport_saigonnewport", "https://eport.saigonnewport.com.vn/ships", "hochiminh",
         "Tan Cang Sai Gon (Cat Lai, Hiep Phuoc): lich tau/chuyen, tra cuu -7/+10 ngay."),
        ("eport_tcit", "https://eport.tcit.com.vn/Ships", "vungtau",
         "TCIT (Cai Mep - Thi Vai): lich cau ben container."),
        ("eport_thanhphuoc", "https://eport.cangthanhphuoc.com/", "dongnai",
         "Cang Thanh Phuoc (Dong Nai)."),
        ("danangport_schedule", "https://danangport.com/dich-vu-khach-hang/lich-tau-container/",
         "danang", "Lich tau container cang Da Nang."),
        ("dinhvuport_shipplan", "https://dinhvuport.com.vn/vn/shipplan.html", "haiphong",
         "Ke hoach tau cang Dinh Vu (Hai Phong)."),
    ]
    return [
        HtmlTableSource(
            name=name, kind="terminal", url_template=url, homepage=url,
            coverage=note, horizon_days=14, global_source=True, port_key=port_key,
        )
        for name, url, port_key, note in configs
    ]


def _carriers():
    """Lich tau hang tau - nguon duy nhat phu duoc tam nhin 15-30 ngay."""
    return [
        HtmlTableSource(
            name="anl_port_schedule",
            kind="carrier",
            url_template=("https://anl.com.au/ebusiness/schedules/port/export"
                          "?countryCode=VN&delayFrom=0&delayTo=30&portCode={unlocode}"
                          "&portName=&fileType=html&isDeparture=False"),
            homepage="https://anl.com.au/ebusiness/schedules",
            coverage="Lich cap cang cua ANL/CMA CGM theo cang, tam nhin toi ~30 ngay.",
            horizon_days=30,
            id_field="unlocode",
        ),
        HtmlTableSource(
            name="sailingschedule_vn",
            kind="carrier",
            url_template="http://www.sailingschedule.com.vn/kht-{key}.html?lang=vi",
            homepage="http://www.sailingschedule.com.vn/",
            coverage="Trang tong hop 'ke hoach tau' theo tung cang vu tai Viet Nam.",
            horizon_days=14,
            id_field="key",
        ),
    ]


def all_sources():
    """Toan bo nguon da cau hinh, theo thu tu uu tien khi hop nhat du lieu."""
    return _port_authorities() + _terminals() + _ais_web() + build_api_sources() + _carriers()


# Do tin cay khi hop nhat ban ghi trung nhau: so lon hon thang.
SOURCE_PRIORITY = {
    "port_authority": 100,
    "terminal": 80,
    "ais": 60,
    "carrier": 40,
    "unknown": 10,
}


def get_sources(names=None, kinds=None):
    sources = all_sources()
    if names and "all" not in names:
        wanted = {n.lower() for n in names}
        sources = [s for s in sources if s.name.lower() in wanted]
    if kinds and "all" not in kinds:
        wanted_kinds = {k.lower() for k in kinds}
        sources = [s for s in sources if s.kind in wanted_kinds]
    return sources
