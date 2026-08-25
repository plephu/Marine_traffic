"""Giao dien dong lenh: thu thap tau du kien cap cang Viet Nam trong 0-30 ngay toi."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

from .aggregate import deduplicate, filter_window, sort_arrivals, summarize
from .dates import now_vn
from .export import to_markdown, write_csv, write_json, write_markdown
from .http import Fetcher, env_key
from .ports import load_ports, select_ports
from .sources import FetchContext, get_sources


def _split(value):
    return [v.strip() for v in str(value).split(",") if v.strip()]


def cmd_list_sources(args):
    rows = []
    for source in get_sources(_split(args.sources), _split(args.kinds)):
        info = source.describe()
        ok, why = source.available(None)
        info["san_sang"] = "co" if ok else "khong (%s)" % why
        rows.append(info)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print("%-26s %-16s %-7s %-28s %s" % ("NGUON", "LOAI", "NGAY", "SAN SANG", "MO TA"))
    for info in rows:
        print("%-26s %-16s %-7s %-28s %s" % (
            info["name"], info["kind"], info["horizon_days"],
            info["san_sang"], (info["coverage"] or "")[:70]))
    print("\nTong: %d nguon. Chi tiet tung nguon: docs/SOURCES.md" % len(rows))
    return 0


def cmd_list_ports(args):
    ports = select_ports(_split(args.ports)) if args.ports else load_ports()
    if args.json:
        print(json.dumps(ports, ensure_ascii=False, indent=2))
        return 0
    print("%-12s %-34s %-9s %-12s %s" % ("KEY", "TEN CANG", "UNLOCODE", "VF ID", "CANG VU"))
    for port in ports:
        code = port.get("unlocode") or "-"
        if code != "-" and not port.get("unlocode_verified"):
            code += "?"
        print("%-12s %-34s %-9s %-12s %s" % (
            port["key"], port["name"], code,
            port.get("vesselfinder_id") or "-", port.get("authority") or "-"))
    print("\n('?' = ma chua doi chieu voi nguon chinh thuc; sua trong vnports/data_ports.json)")
    return 0


def cmd_doctor(args):
    """Kiem tra tung nguon co truy cap duoc va co doc ra bang khong."""
    ports = select_ports(_split(args.ports))
    fetcher = Fetcher(timeout=args.timeout, retries=1, delay=0.2,
                      dump_dir=args.dump_dir, verbose=True)
    ctx = FetchContext(window_start=now_vn(), window_end=now_vn() + timedelta(days=args.days),
                       ports=ports, fetcher=fetcher, verbose=True)
    print("Kiem tra %d nguon...\n" % len(get_sources(_split(args.sources), _split(args.kinds))))
    ok_count = 0
    for source in get_sources(_split(args.sources), _split(args.kinds)):
        ready, why = source.available(ctx)
        if not ready:
            print("[ BO QUA ] %-26s %s" % (source.name, why))
            continue
        before = len(ctx.errors)
        try:
            arrivals = source.fetch(ctx)
        except Exception as exc:  # nguon loi khong duoc lam gay ca lan chay
            print("[ LOI    ] %-26s %s: %s" % (source.name, type(exc).__name__, exc))
            continue
        new_errors = ctx.errors[before:]
        if arrivals:
            ok_count += 1
            with_eta = sum(1 for a in arrivals if a.eta)
            print("[ OK     ] %-26s %d hang (%d co ETA)" % (source.name, len(arrivals), with_eta))
        elif new_errors:
            print("[ LOI    ] %-26s %s" % (source.name, new_errors[-1].split(" | ")[-1][:90]))
        else:
            print("[ RONG   ] %-26s truy cap duoc nhung khong doc ra bang tau" % source.name)
    print("\n%d nguon tra ve du lieu." % ok_count)
    return 0 if ok_count else 1


def cmd_fetch(args):
    ports = select_ports(_split(args.ports))
    if not ports:
        print("Khong khop cang nao. Xem: vnports list-ports", file=sys.stderr)
        return 2
    start = now_vn() + timedelta(days=args.from_days)
    end = now_vn() + timedelta(days=args.days)
    fetcher = Fetcher(timeout=args.timeout, retries=args.retries, delay=args.delay,
                      dump_dir=args.dump_dir, verbose=args.verbose)
    ctx = FetchContext(window_start=start, window_end=end, ports=ports,
                       fetcher=fetcher, verbose=args.verbose)

    sources = get_sources(_split(args.sources), _split(args.kinds))
    print("Cua so ETA: %s -> %s (%d cang, %d nguon)" % (
        start.strftime("%d/%m/%Y %H:%M"), end.strftime("%d/%m/%Y %H:%M"),
        len(ports), len(sources)))

    raw = []
    for source in sources:
        ready, why = source.available(ctx)
        if not ready:
            ctx.log("bo qua %s: %s" % (source.name, why))
            continue
        print("-> %s" % source.name, flush=True)
        try:
            raw.extend(source.fetch(ctx))
        except Exception as exc:
            ctx.fail(source.name, source.__dict__.get("url_template", ""), exc)

    print("\nThu duoc %d ban ghi tho." % len(raw))
    merged = deduplicate(raw)
    inside = sort_arrivals(filter_window(merged, start, end, require_eta=not args.keep_no_eta))
    stats = summarize(inside)
    print("Sau gop trung: %d | trong cua so: %d" % (len(merged), stats["total"]))
    for name, count in sorted(stats["by_source"].items(), key=lambda kv: -kv[1]):
        print("   %-26s %d" % (name, count))

    if ctx.errors:
        print("\n%d loi khi tai (dung --verbose de xem chi tiet):" % len(ctx.errors))
        for err in ctx.errors[:5]:
            print("   " + err[:140])

    if inside:
        print()
        print(to_markdown(inside, limit=args.preview))
    if args.out:
        writer = {"csv": write_csv, "json": write_json, "md": write_markdown}[args.format]
        path = writer(inside, args.out)
        print("\nDa ghi %d dong vao %s" % (len(inside), path))
    return 0 if inside else 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vnports",
        description="Thu thap thong tin tau bien du kien cap cang Viet Nam tu nhieu nguon.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ports", default="all",
                        help="Danh sach cang, ngan cach dau phay (key/UNLOCODE/ten). Mac dinh: all")
    common.add_argument("--sources", default="all", help="Loc theo ten nguon, ngan cach dau phay")
    common.add_argument("--kinds", default="all",
                        help="Loc theo loai nguon: port_authority,terminal,ais,carrier")
    common.add_argument("--timeout", type=int, default=30)
    common.add_argument("--dump-dir", default=None, help="Luu HTML tho de kiem tra parser")

    p_fetch = sub.add_parser("fetch", parents=[common], help="Tai va tong hop du lieu")
    p_fetch.add_argument("--days", type=int, default=30, help="Gioi han tren cua ETA (ngay). Mac dinh 30")
    p_fetch.add_argument("--from-days", type=float, default=0,
                         help="Gioi han duoi cua ETA (ngay). Dung 1 de chi lay tau den sau 24h")
    p_fetch.add_argument("--out", default=None, help="Duong dan file ket qua")
    p_fetch.add_argument("--format", default="csv", choices=["csv", "json", "md"])
    p_fetch.add_argument("--preview", type=int, default=25, help="So dong in ra man hinh")
    p_fetch.add_argument("--keep-no-eta", action="store_true",
                         help="Giu ca ban ghi khong doc duoc ETA")
    p_fetch.add_argument("--retries", type=int, default=3)
    p_fetch.add_argument("--delay", type=float, default=1.0, help="Nghi giua cac request (giay)")
    p_fetch.add_argument("--verbose", "-v", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_doc = sub.add_parser("doctor", parents=[common],
                           help="Kiem tra nguon nao truy cap va parse duoc tu may hien tai")
    p_doc.add_argument("--days", type=int, default=30)
    p_doc.set_defaults(func=cmd_doctor)

    p_src = sub.add_parser("list-sources", parents=[common], help="Liet ke nguon da cau hinh")
    p_src.add_argument("--json", action="store_true")
    p_src.set_defaults(func=cmd_list_sources)

    p_port = sub.add_parser("list-ports", help="Liet ke danh muc cang")
    p_port.add_argument("--ports", default=None)
    p_port.add_argument("--json", action="store_true")
    p_port.set_defaults(func=cmd_list_ports)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
