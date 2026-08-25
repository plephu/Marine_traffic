# Tất cả các nguồn lấy thông tin tàu sắp cập cảng Việt Nam

Tổng hợp mọi nguồn khả dụng tính đến 08/2026, kèm tầm nhìn ETA thực tế, chi phí và
cách truy cập. Cột **Trong repo** cho biết nguồn đã được cấu hình sẵn trong `vnports`
(xem `python -m vnports list-sources`).

## 0. Điều quan trọng trước tiên: không nguồn miễn phí nào phủ đủ 30 ngày

| Nhóm nguồn | Tầm nhìn ETA thực tế | Vì sao |
|---|---|---|
| Cảng vụ hàng hải (kế hoạch điều động) | **1 – 3 ngày** | Kế hoạch điều động chỉ lập cho ngày hôm nay/ngày mai |
| Terminal / ePort | **7 – 14 ngày** | Lịch cầu bến đặt trước theo tuyến |
| AIS (MarineTraffic, VesselFinder…) | **1 – 7 ngày** | ETA lấy từ khai báo hành trình AIS của tàu, chỉ có khi tàu đã rời cảng trước |
| Lịch tàu hãng tàu (CMA CGM, Maersk, ONE…) | **14 – 45 ngày** | Lịch tuyến cố định công bố trước cả tháng |

Muốn phủ trọn 1 – 30 ngày thì **phải ghép nhiều nhóm**: hãng tàu cho khung xa,
terminal cho khung giữa, cảng vụ + AIS cho 1 – 3 ngày sát giờ (chính xác nhất).
Đó chính là lý do `vnports` gộp dữ liệu theo thứ tự ưu tiên
`port_authority > terminal > ais > carrier`.

---

## 1. Cơ quan quản lý nhà nước — chính thức, miễn phí, không cần key

Đây là nguồn đầy đủ nhất cho vùng nước từng cảng (gồm cả tàu hàng rời, tàu dầu,
tàu nội địa mà các trang AIS thương mại hay bỏ sót).

| Nguồn | URL | Nội dung | Trong repo |
|---|---|---|---|
| Cảng vụ HH Hải Phòng | `csdltau.cangvuhaiphong.gov.vn/pages/ship_plan.aspx?d=N` (`d` = độ lệch ngày) | Kế hoạch điều động tàu theo ngày | ✅ `cvhh_haiphong` |
| Cảng vụ HH Hải Phòng (trang tin) | `cangvuhaiphong.gov.vn/ke-hoach-tau/`, `/thong-bao-tau-den-cang/` | Thông báo tàu đến cảng | — |
| Cảng vụ HH Vũng Tàu | `cangvuhanghaivungtau.gov.vn/Index.aspx?page=khddt&d=N` | Kế hoạch điều động tàu biển; `page=lpttnd` cho phương tiện thủy nội địa | ✅ `cvhh_vungtau` |
| Cảng vụ HH TP.HCM | `cangvuhanghaitphcm.gov.vn/index.aspx?cat=2033&page=shipschedule` | Kế hoạch tàu khu vực TP.HCM | ✅ `cvhh_hcm` |
| Cảng vụ HH Đà Nẵng | `cangvuhanghaidanang.gov.vn/vi/ke-hoach-dieu-dong-tau-thuyen` | Kế hoạch điều động tàu thuyền | ✅ `cvhh_danang` |
| Cảng vụ HH Nha Trang | `cangvuhanghainhatrang.gov.vn/showtv/` | Kế hoạch điều động tàu | ✅ `cvhh_nhatrang` |
| Cảng vụ HH Quảng Ninh | `kht1.cangvuhanghaiquangninh.gov.vn/vitritau.aspx` | Vị trí tàu tại cảng + kế hoạch | ✅ `cvhh_quangninh` |
| Cảng vụ HH Nghệ An | `cangvuhanghainghean.gov.vn` | Kế hoạch điều động tàu (đăng theo bài) | ✅ `cvhh_nghean` |
| Cảng vụ HH Cần Thơ | `cangvuhanghaicantho.gov.vn` | Kế hoạch tàu khu vực ĐBSCL | ✅ `cvhh_cantho` |
| Các cảng vụ còn lại | Thanh Hóa, Hà Tĩnh, Quảng Bình, Quảng Trị, Thừa Thiên Huế, Quảng Ngãi, Bình Định, Bình Thuận, Đồng Nai, Mỹ Tho, An Giang, Kiên Giang, Cà Mau… | Cùng dạng "kế hoạch điều động tàu"; tên miền theo mẫu `cangvuhanghai<tinh>.gov.vn` | thêm vào `sources/catalog.py` |
| Cục Hàng hải & Đường thủy VN | `vimawa.gov.vn` (trước là `vinamarine.gov.vn`) | Văn bản, thống kê, danh mục cảng biển — **không** có ETA từng tàu | — |
| Cổng một cửa quốc gia (VNSW) | `vnsw.gov.vn` | Thủ tục tàu biển điện tử: tàu đến/rời, e-manifest. Dữ liệu đầy đủ nhất nhưng **cần tài khoản doanh nghiệp + chữ ký số**, không mở công khai | — |

Lưu ý kỹ thuật: phần lớn site cảng vụ chạy ASP.NET WebForms, bảng render bằng
`GridView`, một số trang lọc theo ngày bằng POST kèm `__VIEWSTATE`. Nếu tham số
`?d=N` không có tác dụng, hãy dump HTML (`--dump-dir`) rồi bổ sung form POST.

---

## 2. Cảng / terminal — lịch cầu bến, tầm 7 – 14 ngày

| Nguồn | URL | Khu vực | Trong repo |
|---|---|---|---|
| SNP ePort (Tân Cảng Sài Gòn) | `eport.saigonnewport.com.vn/ships` | Cát Lái, Hiệp Phước, TCCT | ✅ `eport_saigonnewport` |
| TCIT ePort | `eport.tcit.com.vn/Ships` | Cái Mép – Thị Vải | ✅ `eport_tcit` |
| Cảng Thạnh Phước | `eport.cangthanhphuoc.com` | Đồng Nai / Bình Dương | ✅ `eport_thanhphuoc` |
| Cảng Đà Nẵng | `danangport.com/dich-vu-khach-hang/lich-tau-container/` | Tiên Sa | ✅ `danangport_schedule` |
| Cảng Đình Vũ | `dinhvuport.com.vn/vn/shipplan.html` | Hải Phòng | ✅ `dinhvuport_shipplan` |
| Gemadept / Gemalink, CMIT, SSIT, SP-PSA | website từng terminal | Cái Mép | thêm thủ công |
| Hateco Hải Phòng, Nam Hải Đình Vũ, Tân Vũ, Chùa Vẽ | website từng terminal | Hải Phòng | thêm thủ công |
| VICT, Tân Thuận, Bến Nghé | website từng terminal | TP.HCM | thêm thủ công |

Nhiều ePort render bảng bằng JavaScript hoặc yêu cầu đăng nhập. Khi `vnports doctor`
báo `RỖNG` cho các nguồn này, cách xử lý theo thứ tự: (1) tìm endpoint JSON mà trang
gọi trong tab Network của trình duyệt và khai báo bằng `JsonApiSource`; (2) nếu bắt
buộc JS, chạy qua Playwright rồi đưa HTML vào `vnports.tables.best_table`.

---

## 3. Trang theo dõi AIS (web) — tầm 1 – 7 ngày

| Nguồn | URL mẫu | Ghi chú | Trong repo |
|---|---|---|---|
| VesselFinder | `vesselfinder.com/ports/VNSGN001` (Hải Phòng `VNHPH001`, Nha Trang `VNNHA001`) | Có mục "Expected arrivals" miễn phí, giới hạn số dòng | ✅ `vesselfinder_expected`, `vesselfinder_port` |
| MyShipTracking | `myshiptracking.com/ports/port-of-hai-phong-in-vn-vietnam-id-4079` | ID cảng nằm ngay trong URL | ✅ `myshiptracking_port` |
| MarineTraffic (Kpler) | `marinetraffic.com/en/ais/details/ports/1726` (TP.HCM) | Dữ liệu tốt nhất nhưng **chặn bot bằng Cloudflare** — nên dùng API | ✅ `marinetraffic_port_web` |
| AllTrack | `alltrack.org/list-port-of-calls-1726-vnsgn-ho-chi-minh` | Danh sách port call miễn phí, hữu ích để đối chiếu chéo | ✅ `alltrack_portcalls` |
| Shipnext | `shipnext.com/port/582472ccc9c19c0be8d8cb8d` (TP.HCM) | Arrivals/departures/expected | thêm thủ công |
| FleetMon | `fleetmon.com/ports/...` | Cần tài khoản cho dữ liệu đầy đủ | — |
| VesselTracker, Balticshipping, Shipfinder | web tương ứng | Chất lượng dữ liệu VN thấp hơn | — |

**Điều khoản sử dụng:** MarineTraffic và VesselFinder cấm cào dữ liệu tự động trong
ToS. Dùng bản web để tra cứu thủ công thì được, còn chạy tự động định kỳ thì nên mua
API tương ứng (mục 4). Site cảng vụ `.gov.vn` là thông tin công khai, nhưng vẫn nên
giữ nhịp request thưa (`--delay`).

---

## 4. API AIS thương mại — cách hợp lệ để chạy tự động

| Nhà cung cấp | Endpoint "tàu dự kiến đến cảng" | Giá tham khảo 2026 | Trong repo |
|---|---|---|---|
| MarineTraffic / Kpler | `services.marinetraffic.com/api/expectedarrivals/v:2/{key}/portid:{id}/protocol:jsono` | Chỉ bán gói doanh nghiệp, phải liên hệ sales | ✅ `marinetraffic_api` (`MARINETRAFFIC_API_KEY`) |
| VesselFinder | `api.vesselfinder.com/expectedarrivals?userkey={key}&unlocode={code}` — [tài liệu](https://api.vesselfinder.com/docs/expectedarrivals.html) | Trả theo credit | ✅ `vesselfinder_api` (`VESSELFINDER_API_KEY`) |
| Datalastic | Không có endpoint expected-arrivals theo cảng; phải suy ra từ `vessel_inradius` + trường `destination`/`eta` | từ ~99 EUR/tháng | ⚠️ `datalastic_api` (tắt sẵn) |
| AISStream.io | WebSocket AIS realtime **miễn phí** — tự lọc bản tin message type 5 (destination + ETA) trong vùng biển VN | Miễn phí, cần đăng ký key | thêm thủ công |
| AISHub | Trao đổi dữ liệu: đóng góp một trạm AIS thì được lấy feed | Miễn phí có điều kiện | — |
| Spire Maritime, ORBCOMM | AIS vệ tinh, phủ cả tàu ngoài khơi xa | Doanh nghiệp | — |
| SeaVantage, Portcast, Searoutes | ETA dự báo bằng ML cho container, chính xác hơn ETA khai báo | Doanh nghiệp | — |

Nếu cần tầm nhìn dài mà vẫn tự động: AISStream.io (miễn phí) cho vị trí realtime,
ghép với lịch hãng tàu ở mục 5 là phương án rẻ nhất.

---

## 5. Hãng tàu & tổng hợp lịch tàu — nguồn duy nhất phủ tới 30 ngày

| Nguồn | URL | Ghi chú | Trong repo |
|---|---|---|---|
| ANL / CMA CGM | `anl.com.au/ebusiness/schedules/port/export?countryCode=VN&portCode=VNSGN&delayTo=30…` | Xuất lịch theo cảng, tham số `delayFrom`/`delayTo` tính bằng ngày | ✅ `anl_port_schedule` |
| sailingschedule.com.vn | `sailingschedule.com.vn/kht-ho-chi-minh.html` | Tổng hợp "kế hoạch tàu" theo từng cảng vụ VN | ✅ `sailingschedule_vn` |
| Maersk | Schedules API trên `developer.maersk.com` | Cần đăng ký app, có gói miễn phí giới hạn | thêm thủ công |
| ONE | `ecomm.one-line.com/one-ecom/schedule/vessel-schedule` | Trang JS, cần Playwright hoặc API đối tác | — |
| MSC, Evergreen, HMM, Wan Hai, SITC, Yang Ming, COSCO | trang "vessel schedule" của từng hãng | Định dạng khác nhau, nhiều hãng có PDF | — |
| Flexport Atlas | `atlas.flexport.com/oceanport/locode:VNSGN/...` | Lịch tàu + thống kê cảng, miễn phí xem | — |
| lichtau.com, shippingschedule.com.vn | | Tổng hợp lịch tàu tiếng Việt | — |

---

## 6. Chiến lược khuyến nghị theo mục đích

- **Cần chính xác cho 1 – 3 ngày tới** (điều độ, đại lý, giao nhận): cảng vụ hàng hải
  là chuẩn, đối chiếu thêm AIS. → `--kinds port_authority,ais --days 3`
- **Lập kế hoạch 1 – 4 tuần** (kho bãi, vận tải bộ): lịch hãng tàu + terminal.
  → `--kinds carrier,terminal --days 30`
- **Chạy sản xuất, tự động, hợp pháp**: VesselFinder API hoặc MarineTraffic API cho
  AIS + cào site `.gov.vn` với nhịp thưa + lịch hãng tàu.
- **Ngân sách 0 đồng**: cảng vụ + ePort terminal + AISStream.io.

## 7. Trạng thái kiểm chứng

Bộ mã này được viết trong môi trường **bị chặn toàn bộ egress** (proxy trả 403 cho mọi
host ngoài), nên các URL trên lấy từ kết quả tìm kiếm và tài liệu công khai, **chưa
được đối chiếu với HTML thật**. Trước khi dùng thật, chạy trên máy có mạng:

```bash
python -m vnports doctor --dump-dir raw/
```

Lệnh này báo từng nguồn là `OK` / `RỖNG` / `LỖI` và lưu HTML thô vào `raw/` để chỉnh
bộ nhận diện cột trong `vnports/tables.py` nếu cần.
