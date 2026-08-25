"""Kiem thu offline: parser va pipeline chay tren HTML mau, khong can mang."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vnports.aggregate import deduplicate, filter_window
from vnports.dates import VN_TZ, parse_datetime
from vnports.models import VesselArrival, normalize_name, valid_imo
from vnports.sources.base import FetchContext, HtmlTableSource
from vnports.tables import best_table, map_header

FIXTURES = Path(__file__).parent / "fixtures"
REF = datetime(2026, 8, 25, 12, 0, tzinfo=VN_TZ)


class FakeFetcher:
    """Thay the Fetcher trong kiem thu: tra ve HTML co san theo URL."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_text(self, url, **kwargs):
        self.calls.append(url)
        for fragment, html in self.pages.items():
            if fragment in url:
                return html
        raise RuntimeError("khong co trang mau cho " + url)


class TestDates(unittest.TestCase):
    def test_formats(self):
        cases = {
            "26/08/2026 05:30": datetime(2026, 8, 26, 5, 30, tzinfo=VN_TZ),
            "2026-08-26 05:30": datetime(2026, 8, 26, 5, 30, tzinfo=VN_TZ),
            "Aug 28, 2026 03:20": datetime(2026, 8, 28, 3, 20, tzinfo=VN_TZ),
            "28 Aug 2026 03:20": datetime(2026, 8, 28, 3, 20, tzinfo=VN_TZ),
            "26/08 05h30": datetime(2026, 8, 26, 5, 30, tzinfo=VN_TZ),
        }
        for text, expected in cases.items():
            self.assertEqual(parse_datetime(text, ref=REF), expected, text)

    def test_empty_values(self):
        for text in ["", "-", "N/A", None, "khong xac dinh"]:
            self.assertIsNone(parse_datetime(text, ref=REF))

    def test_year_inferred_from_reference(self):
        # Thang 1 nhin tu cuoi thang 12 phai roi vao nam sau.
        ref = datetime(2026, 12, 28, tzinfo=VN_TZ)
        self.assertEqual(parse_datetime("03/01 08:00", ref=ref).year, 2027)


class TestHeaderMapping(unittest.TestCase):
    def test_vietnamese_and_english(self):
        self.assertEqual(map_header("Tên tàu"), "vessel_name")
        self.assertEqual(map_header("Thời gian đến"), "eta")
        self.assertEqual(map_header("ETA"), "eta")
        self.assertEqual(map_header("Đại lý"), "agent")
        self.assertEqual(map_header("Hô hiệu"), "call_sign")
        self.assertIsNone(map_header("TT"))


class TestTableExtraction(unittest.TestCase):
    def test_port_authority_table(self):
        rows = best_table((FIXTURES / "cangvu_ship_plan.html").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["vessel_name"], "HAI NAM 68")
        self.assertEqual(rows[1]["imo"], "9525663")
        self.assertEqual(rows[2]["agent"], "SITC VIỆT NAM")

    def test_vesselfinder_table(self):
        rows = best_table((FIXTURES / "vesselfinder_expected.html").read_text(encoding="utf-8"))
        self.assertEqual([r["vessel_name"] for r in rows],
                         ["EVER LOTUS", "NORD SUPERIOR", "GAS ARIES"])
        self.assertEqual(rows[0]["from_port"], "KAOHSIUNG")


class TestModels(unittest.TestCase):
    def test_imo_checksum(self):
        self.assertEqual(valid_imo("9525663"), "9525663")
        self.assertIsNone(valid_imo("9525664"))   # sai check digit
        self.assertIsNone(valid_imo("12345"))

    def test_identity_prefers_imo(self):
        self.assertEqual(VesselArrival(vessel_name="A", imo="9525663").identity,
                         ("imo", "9525663"))
        self.assertEqual(VesselArrival(vessel_name="Ever  Lotus").identity,
                         ("name", "EVERLOTUS"))
        self.assertEqual(normalize_name("Ever-Lotus "), "EVERLOTUS")


class TestSourcePipeline(unittest.TestCase):
    def _ctx(self, fetcher, ports):
        return FetchContext(window_start=REF, window_end=REF + timedelta(days=30),
                            ports=ports, fetcher=fetcher)

    def test_html_source_to_arrivals(self):
        source = HtmlTableSource(
            name="cvhh_test", kind="port_authority",
            url_template="https://example.test/ship_plan?d={d}",
            day_offsets=[0], horizon_days=1, global_source=True, port_key="haiphong")
        fetcher = FakeFetcher({"ship_plan": (FIXTURES / "cangvu_ship_plan.html").read_text(encoding="utf-8")})
        arrivals = source.fetch(self._ctx(fetcher, []))
        self.assertEqual(len(arrivals), 3)
        first = arrivals[0]
        self.assertEqual(first.vessel_name, "HAI NAM 68")
        self.assertEqual(first.imo, "9188219")
        self.assertEqual(first.source_kind, "port_authority")
        self.assertEqual(first.port_name, "haiphong")
        self.assertIsNotNone(first.eta)

    def test_source_skipped_without_id(self):
        source = HtmlTableSource(name="vf", kind="ais",
                                 url_template="https://example.test/{vf_id}",
                                 id_field="vesselfinder_id")
        fetcher = FakeFetcher({})
        arrivals = source.fetch(self._ctx(fetcher, [{"key": "cantho", "vesselfinder_id": None}]))
        self.assertEqual(arrivals, [])
        self.assertEqual(fetcher.calls, [])  # khong goi mang khi thieu ID

    def test_fetch_errors_are_collected_not_raised(self):
        source = HtmlTableSource(name="broken", kind="ais",
                                 url_template="https://example.test/missing",
                                 global_source=True, port_key="x")
        ctx = self._ctx(FakeFetcher({}), [])
        self.assertEqual(source.fetch(ctx), [])
        self.assertEqual(len(ctx.errors), 1)


class TestAggregation(unittest.TestCase):
    def test_merge_across_sources_and_window(self):
        official = VesselArrival(vessel_name="MAERSK NEWPORT", imo="9525663",
                                 eta=REF + timedelta(days=2), port_name="Hai Phong",
                                 berth="Cầu số 1", source="cvhh_haiphong",
                                 source_kind="port_authority")
        ais = VesselArrival(vessel_name="Maersk Newport", eta=REF + timedelta(days=2, hours=4),
                            port_name="Hai Phong", flag="Singapore",
                            source="vesselfinder_expected", source_kind="ais")
        far = VesselArrival(vessel_name="LATE SHIP", eta=REF + timedelta(days=45),
                            port_name="Hai Phong", source="anl", source_kind="carrier")

        merged = deduplicate([ais, official, far])
        self.assertEqual(len(merged), 2)
        primary = merged[0]
        self.assertEqual(primary.source, "cvhh_haiphong")  # nguon chinh thuc duoc uu tien
        self.assertEqual(primary.berth, "Cầu số 1")
        self.assertEqual(primary.flag, "Singapore")        # bo sung tu nguon AIS
        self.assertIn("vesselfinder_expected", primary.raw["_merged_sources"])

        inside = filter_window(merged, REF, REF + timedelta(days=30))
        self.assertEqual([a.vessel_name for a in inside], ["MAERSK NEWPORT"])

    def test_records_without_eta_dropped_by_default(self):
        no_eta = VesselArrival(vessel_name="GAS ARIES", port_name="Hai Phong",
                               source="vf", source_kind="ais")
        self.assertEqual(filter_window([no_eta], REF, REF + timedelta(days=30)), [])
        self.assertEqual(len(filter_window([no_eta], REF, REF + timedelta(days=30),
                                           require_eta=False)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
