# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung |
| --------------- | ------------ |
| Họ và tên       | Nguyễn Văn An |
| MSSV            | 01817 |
| Khóa/Lớp        | K3 |
| Vai trò chính   | Role 2 — Order & Seller Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| In-Memory Data Store | `src/data_store.py` (`DataStore.get_instance`) | 3 file CSV: `olist_orders`, `olist_order_items`, `olist_sellers` | DataStore instance hỗ trợ tra cứu $O(1)$ | Hoàn thành |
| Order & Seller Agent | `src/agents/order_seller_agent.py` (`OrderSellerAgent.process`) | `case_id`, `claimed_order_id` | `AgentResponse` JSON facts, entity_ids, evidence_ids | Hoàn thành |
| Data Contracts | `src/contracts.py` | Specifications đề bài | TypedDict definitions (`OrderSellerFacts`, `AgentResponse`,...) | Hoàn thành |
| Demo & Unit Test | `run_role2_demo.py`, `tests/test_order_seller_agent.py` | Case ID (`EC_001` đến `EC_050`) | Kết quả kiểm thử facts và evidence IDs | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ------------------------- | ----------------------------- | ----------------------- |
| Thống nhất Data Contract | Member 1 (Coordinator), Member 3 (Payment), Member 4 (Policy) | Thống nhất định dạng JSON response và kiểu dữ liệu `Decimal` cho tiền tệ |
| Chuẩn bị script demo | Cả nhóm | Tạo `run_role2_demo.py` hỗ trợ test bất kỳ case nào từ `EC_001` đến `EC_050` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Xây dựng In-memory CSV DataStore | `src/data_store.py` | Load 99,441 orders, 98,666 order items, 3,095 sellers | `python run_role2_demo.py 1` |
| Phân tích đơn hàng & phát hiện bàn giao trễ | `src/agents/order_seller_agent.py` | Trích xuất mốc thời gian, tính `item_total_brl`, `freight_total_brl`, xác định `is_seller_late_handoff` | `python run_role2_demo.py 10` |
| Sinh Evidence IDs đúng quy định đề bài | `src/agents/order_seller_agent.py` | Bằng chứng chuẩn `order:<id>`, `item:<order_id>:<item_id>`, `seller:<seller_id>` | Log đối chiếu JSON output |

**Mô tả kết quả cụ thể:**
Đã xử lý trích xuất chính xác 100% dữ liệu đơn hàng cho 50 case (`EC_001` đến `EC_050`), phát hiện chính xác trường hợp seller giao trễ cho bên vận chuyển (như `EC_001` bị trễ bàn giao 9 ngày) và tính tiền tệ chuẩn xác 2 chữ số thập phân bằng kiểu Decimal.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Đơn hàng thương mại điện tử Olist chứa thông tin phân tán ở nhiều CSV. Cần truy xuất nhanh thông tin đơn hàng, giá tiền sản phẩm, phí vận chuyển và kiểm tra xem Seller có giao hàng trễ cho shipper không (`order_delivered_carrier_date > shipping_limit_date`).

### Cách triển khai
- **DataStore**: Khởi tạo Singleton nạp dữ liệu 3 file CSV vào RAM theo Hash Map `O(1)` với khóa chính `order_id`. Tự động chuẩn hóa xóa bỏ khoảng trắng và dấu ngoặc kép thừa.
- **OrderSellerAgent**: 
  1. Tra cứu `claimed_order_id` từ `DataStore`.
  2. Dùng kiểu `Decimal` với `ROUND_HALF_UP` để tính `item_total_brl` và `freight_total_brl`.
  3. So sánh chuỗi thời gian ISO `order_delivered_carrier_date` với `shipping_limit_date` của từng item. Đánh dấu `is_seller_late_handoff = True` nếu quá hạn.
  4. Tạo danh sách `entity_ids` và `evidence_ids` theo đúng định dạng `order:<id>`, `item:<order_id>:<item_id>`, `seller:<seller_id>`.

### Input, output và contract

| Thành phần | Mô tả |
| ----------------------- | -------------------------------------- |
| Input | `case_id: str`, `claimed_order_id: str` |
| Output | `AgentResponse` chứa `facts` (`order_status`, `item_total_brl`, `freight_total_brl`, `late_sellers`), `entity_ids`, `evidence_ids` |
| Module phụ thuộc | `data/olist_orders_dataset.csv`, `data/olist_order_items_dataset.csv`, `data/olist_sellers_dataset.csv` |
| Module sử dụng output | `CoordinatorAgent` (Role 1), `PaymentAgent` (Role 3), `PolicyAgent` (Role 4) |
| Điều kiện lỗi cần xử lý | Order không tồn tại trong CSV (trả về `status: "error"` và danh sách lỗi) |

### Cách xác minh

```bash
python run_role2_demo.py 10
```

- **Kết quả mong đợi:** In ra JSON response của case `EC_010`, `order_status` = `"delivered"`, `item_total_brl` = `"19.99"`, `freight_total_brl` = `"7.78"`, `is_seller_late_handoff` = `False`.
- **Kết quả thực tế:** Khớp 100% kết quả mong đợi.
- **Artifact/log:** File `run_role2_demo.py` và `tests/test_order_seller_agent.py`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn phương pháp tính tiền (`item_total_brl`, `freight_total_brl`) để tránh sai số tài chính.
- **Các phương án đã cân nhắc:**
  1. Dùng kiểu số thực `float` mặc định của Python.
  2. Dùng module `decimal.Decimal` với cấu hình làm tròn `ROUND_HALF_UP` 2 chữ số thập phân.
- **Phương án đã chọn:** Phương án 2 (`decimal.Decimal`).
- **Lý do:** Binary float trong máy tính dễ phát sinh các sai số vô hạn tuần hoàn (ví dụ `0.1 + 0.2 = 0.30000000000000004`), dẫn đến sai lệch khi đối soát tài chính. `Decimal` đảm bảo độ chính xác tuyệt đối.
- **Bằng chứng quyết định phù hợp:** Kết quả `item_total_brl` và `freight_total_brl` luôn ra định dạng chuỗi 2 chữ số thập phân chuẩn xác (`119.90`, `12.04`).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Chuỗi dữ liệu CSV chứa các khoảng trắng và dấu ngoặc kép thừa (ví dụ `"order_id"` hoặc `" 53cdb2fc... "`) dẫn đến tra cứu Hash Map bị thất bại (KeyError / Not Found).
- **Lệnh hoặc bước tái hiện:** `DataStore.get_instance().get_order("e2a03ccf5ea816036608b2d8c3ab8e60")` trả về `None`.
- **Nguyên nhân gốc:** Trình đọc CSV không tự động loại bỏ dấu ngoặc kép bọc ngoài chuỗi giá trị trong một số dòng dữ liệu Olist.
- **Cách xử lý:** Thêm xử lý chuỗi `.strip('"').strip()` cho tất cả các key và value trong quá trình nạp dữ liệu CSV ở `src/data_store.py`.
- **Cách xác minh sau khi sửa:** Chạy lại `python run_role2_demo.py 1`, đơn hàng được tìm thấy thành công.
- **Điều học được:** Luôn làm sạch (sanitize/strip) dữ liệu đầu vào từ CSV trước khi đưa vào indexing.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Input JSON đến Output JSON như thế nào?**
   - Coordinator tiếp nhận `input/EC_xxx.json`, trích xuất `claimed_order_id`. OrderSellerAgent (Role 2) tra CSV nạp facts đơn hàng & seller. PaymentAgent (Role 3) tra CSV nạp facts thanh toán & đối soát. Delivery/PolicyAgent (Role 4) phân tích giao trễ và áp quy tắc `EC_POLICY_V1` để ra quyết định hoàn tiền. VerifierAgent kiểm tra độc lập trước khi ghi `output/EC_xxx.json`.
2. **Vai trò của Evidence IDs trong việc đánh giá kết quả:**
   - Evidence IDs đóng vai trò là bằng chứng có thể kiểm chứng độc lập (verifiable facts). Đề bài phạt điểm nặng (false positive) nếu hệ thống đưa vào các bằng chứng không tồn tại hoặc sai format (`order:<id>`, `item:<order_id>:<item_id>`, `seller:<seller_id>`).
3. **Vì sao phải tách biệt dữ liệu Order facts và Payment facts giữa các Agent?**
   - Kiến trúc Multi-Agent A2A yêu cầu mỗi agent quản lý một miền tri thức (domain) riêng biệt, thực hiện phân công công việc (separation of concerns) và kiểm chứng độc lập trước khi Coordinator tổng hợp.
4. **Tại sao phải nạp CSV 1 lần vào memory thay vì đọc CSV theo từng case?**
   - Với 50 case input, việc đọc lại 3 file CSV nặng hàng chục MB 50 lần sẽ làm tăng thời gian thực thi lên gấp hàng trăm lần. Nạp vào Hash Map $O(1)$ 1 lần duy nhất giúp hệ thống hoàn thành 50 case trong vài giây.
5. **Tiêu chí đánh giá hệ thống xử lý khiếu nại thành công:**
   - Đúng `primary_issue` (20%), Đúng `affected_entities` (20%), Đúng `financial_resolution` (20%), Đúng `root_cause_analysis` (15%), Đúng `evidence_ids` (15%), và Đúng `resolution_actions` (10%).

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Văn An  
**Ngày xác nhận:** 2026-08-05
