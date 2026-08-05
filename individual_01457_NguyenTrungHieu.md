# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                        |
| --------------- | -------------------------------- |
| Họ và tên       | Nguyễn Trung Hiếu                |
| MSSV            | 01457                            |
| Khóa/Lớp        | K3                                |
| Vai trò chính   | Payment Agent (Thành viên 3)     |
| Ngày hoàn thành | 2026-08-05                       |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                          | File/hàm phụ trách                                          | Input nhận vào                                                                     | Output bàn giao                                                                                          | Trạng thái  |
| -------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ----------- |
| Payment Agent (đối soát thanh toán)          | `src/agents/payment_agent.py` (`PaymentAgent`, `PaymentIndex`) | `{case_id, order_id, policy_version, item_total_brl, freight_total_brl}`             | `{agent, case_id, status, facts:{payment_total_brl, payment_row_count, is_reconciled, valid_split_payment}, payment_ids, evidence_ids, errors}` | Hoàn thành  |
| Money helper dùng chung                      | `src/money.py` (`to_decimal`, `money_str`)                   | Giá trị thô từ CSV/JSON                                                              | `Decimal` làm tròn 2 chữ số (`ROUND_HALF_UP`)                                                             | Hoàn thành  |
| Bộ test unit + integration cho Payment Agent | `tests/test_payment_agent.py`                                 | Fixture CSV giả lập + dữ liệu Olist thật trong `data/`                               | 23 test case / 50 subtest (bao gồm smoke test chạy toàn bộ 50 case trong `input/`)                        | Hoàn thành  |

Không nhận ownership phần Coordinator, Order & Seller Agent, Delivery/Policy/Verifier Agent — các phần này do Thành viên 1, 2, 4 phụ trách.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                                                                                                    | Thành viên/module được hỗ trợ                          | Kết quả                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phát hiện và tái hiện lỗi contract: `OrderSellerAgent` trả ID trong key lồng `entity_ids` thay vì field phẳng `order_ids/item_ids/seller_ids` mà `PolicyAgent` mong đợi | Thành viên 2 (Order & Seller Agent), Thành viên 4 (Policy Agent) | Script tái hiện bằng dữ liệu thật (case `EC_001`) cho thấy `affected_entities.order_ids/item_ids/seller_ids` bị rỗng dù dữ liệu gốc đúng; đã báo lại nhóm, đề xuất hướng sửa. Xem chi tiết mục 6. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                                    | File/hàm/artifact liên quan                                  | Kết quả bàn giao                                                    | Cách xác minh                                                       |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Đối soát `payment_total_brl` với `item_total + freight_total` trong sai số 0.10 BRL, xác định `valid_split_payment` | `src/agents/payment_agent.py`                                    | `PaymentAgent.run()` trả facts + evidence hợp lệ                    | `pytest tests/test_payment_agent.py -v` → 23 passed                    |
| Tích hợp thật với `PolicyAgent`/`VerifierAgent` (code của Thành viên 4), không phải mock giả định | `tests/test_payment_agent.py::PaymentPolicyIntegrationTests`     | Proposal do `PolicyAgent` sinh ra từ output `PaymentAgent` được `VerifierAgent` chấp nhận (`valid: True`) | `pytest tests/test_payment_agent.py::PaymentPolicyIntegrationTests -v` |
| Chạy `PaymentAgent` trên toàn bộ 50 case thật trong `input/` với dữ liệu CSV thật trong `data/`     | `tests/test_payment_agent.py::PaymentAgentRealDatasetTests`      | 50/50 case trả `status: success`, `payment_total_brl` đúng định dạng 2 chữ số | `pytest tests/test_payment_agent.py -k RealDataset -v`                 |

Output cụ thể để xác minh: chạy `PaymentAgent` cho case `EC_001` (order `e2a03ccf5ea816036608b2d8c3ab8e60`) trả về `payment_total_brl: "131.94"`, `payment_row_count: 1` — đối chiếu tay bằng `grep` trực tiếp trên `data/olist_order_payments_dataset.csv` cho kết quả khớp chính xác.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Payment Agent phải xác định order đã được thanh toán đủ hay chưa để `PolicyAgent` áp đúng rule: `canceled_order_paid`/`unavailable_order_paid` cần `payment_total > 0`, `valid_split_payment` cần ≥2 payment row và tổng khớp, các rule giao trễ cần biết `payment_total_brl` để tính refund khi issue là `platform`. Nếu Payment Agent tính sai (ví dụ nhân `payment_value` với `payment_installments`, hoặc cộng bằng `float`), toàn bộ quyết định policy và số tiền hoàn ở downstream sẽ sai theo mà không có cách nào tự phát hiện.

### Cách triển khai

`PaymentIndex` đọc `olist_order_payments_dataset.csv` đúng một lần khi khởi tạo bằng `csv.DictReader`, gom row theo `order_id` vào dict — tránh đọc lại CSV cho từng case. `PaymentAgent.run()` cộng `payment_value` bằng `Decimal` (qua `src/money.py`, làm tròn `ROUND_HALF_UP`), không dùng `payment_installments` trong bất kỳ phép tính nào. `is_reconciled` được xác định bằng `abs(payment_total - (item_total + freight_total)) <= 0.10`; `valid_split_payment` chỉ đúng khi có ≥2 payment row **và** đã reconciled. Envelope trả về khớp đúng với những gì `PolicyAgent._facts()` (code của Thành viên 4) đọc — điều này được xác nhận bằng cách chạy `PaymentAgent` thật rồi đưa thẳng output vào `PolicyAgent`/`VerifierAgent` thật, không dựa vào giả định.

### Input, output và contract

| Thành phần              | Mô tả                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Input                    | `{case_id, order_id, policy_version, item_total_brl, freight_total_brl}` — 2 field cuối do Order & Seller Agent cung cấp qua Coordinator |
| Output                   | `{agent: "payment_agent", case_id, status, facts:{payment_total_brl, payment_row_count, is_reconciled, valid_split_payment}, payment_ids, evidence_ids, errors}` |
| Module phụ thuộc         | `data/olist_order_payments_dataset.csv`, `src/money.py`                                                     |
| Module sử dụng output    | `src/agents/policy_agent.py` (Thành viên 4)                                                                  |
| Điều kiện lỗi cần xử lý  | `order_id` rỗng/thiếu trong request → `status: "error"`; order không có payment row nào → **không phải lỗi**, trả `payment_total_brl: "0.00"` (một số order canceled/unavailable hợp lệ không có payment) |

### Cách xác minh

```bash
.venv/Scripts/python.exe -m pytest tests/test_payment_agent.py -v
```

- **Kết quả mong đợi:** toàn bộ test pass, gồm 4 case bắt buộc theo phân công (đơn/split/lệch tiền/không payment) cộng các case biên và smoke test 50 case thật.
- **Kết quả thực tế:** `23 passed, 50 subtests passed` — không có test nào fail hoặc skip (dataset thật trong `data/` và 50 file `input/` đều có mặt trong checkout).
- **Artifact/log:** `tests/test_payment_agent.py`; output terminal của lệnh pytest ở trên.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Chọn cách đọc CSV và kiểu dữ liệu để cộng tiền BRL.
- **Các phương án đã cân nhắc:**
  1. Dùng `pandas.read_csv` — nhanh, ít code, nhưng mặc định parse cột số ra `float64`.
  2. Dùng `csv.DictReader` (stdlib) + `Decimal` cho mọi phép cộng/so sánh tiền.
- **Phương án đã chọn:** (2) — stdlib `csv` + `Decimal`.
- **Lý do:** `float64` gây sai số nhị phân kinh điển khi cộng tiền (ví dụ `0.1 + 0.2 != 0.3`) — đây đúng là lỗi mà README liệt kê là "lỗi dễ gặp" của bài. `Decimal` với `quantize(..., ROUND_HALF_UP)` đảm bảo làm tròn 2 chữ số chính xác và kết quả lặp lại được giữa các lần chạy, đánh đổi bằng việc phải tự viết code đọc/parse CSV thay vì dùng 1 dòng `pandas`.
- **Bằng chứng quyết định phù hợp:** `test_installments_are_not_multiplied_into_total`, `test_zero_value_row_still_counts_toward_row_count_and_total` và toàn bộ test tiền tệ khác đều pass với giá trị đúng đến 2 chữ số thập phân; đối chiếu tay với `data/olist_order_payments_dataset.csv` cho case `EC_001` khớp chính xác `131.94`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi lấy output thật của `OrderSellerAgent` (Thành viên 2) làm `order_facts` đưa vào `PolicyAgent` (Thành viên 4), `proposal["affected_entities"]` trả về `order_ids`, `item_ids`, `seller_ids` đều **rỗng** dù dữ liệu gốc từ `OrderSellerAgent` là đúng.
- **Lệnh hoặc bước tái hiện:**
  ```python
  order_result = OrderSellerAgent().process(case_id="EC_001", claimed_order_id="e2a03ccf5ea816036608b2d8c3ab8e60")
  proposal = PolicyAgent().run({"case_id": "EC_001", "policy_version": "EC_POLICY_V1",
      "order_facts": order_result, "payment_facts": payment_facts, "delivery_facts": delivery_facts})["proposal"]
  print(proposal["affected_entities"])  # order_ids/item_ids/seller_ids đều []
  ```
- **Nguyên nhân gốc:** `OrderSellerAgent` trả entity ID trong key lồng `entity_ids: {order_ids, item_ids, seller_ids, payment_ids}`, trong khi `PolicyAgent._facts()` chỉ đọc các field này khi chúng nằm **phẳng ở top-level** của envelope (đúng convention mà `PaymentAgent` đang dùng cho `payment_ids`, và đúng mô tả gốc trong tài liệu phân công chung). `evidence_ids` không bị ảnh hưởng vì field này vốn đã nằm top-level ở cả hai phía.
- **Cách xử lý:** *Chưa xử lý* — đã xác định chính xác root cause và báo lại cho nhóm (Thành viên 1, 2, 4) kèm script tái hiện; đề xuất sửa tại `OrderSellerAgent` (đổi `entity_ids` lồng thành field phẳng) vì `PolicyAgent`/`VerifierAgent` đã merge và có test pass dựa trên format phẳng.
- **Cách xác minh sau khi sửa:** Chưa thực hiện — sẽ chạy lại script tái hiện ở trên và kỳ vọng `affected_entities.order_ids/item_ids/seller_ids` khớp đúng ID gốc.
- **Điều học được:** `VerifierAgent` hiện tại chỉ kiểm tra giới hạn số lượng phần tử (`<= 5`), không kiểm tra list rỗng có hợp lý hay không, nên lỗi loại này lọt qua verification một cách âm thầm trên cả 50 case. Test tích hợp bằng dữ liệu thật giữa các agent (không chỉ mock nội bộ từng agent) là cách duy nhất phát hiện được lớp lỗi contract này.

Chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** `affected_entities.order_ids/item_ids/seller_ids` của toàn bộ output cuối cùng — vì `OrderSellerAgent` luôn trả `entity_ids` lồng, lỗi này ảnh hưởng tất cả 50 case nếu không sửa trước khi nộp.
- **Những gì đã loại trừ:** Đã xác nhận `evidence_ids` không bị ảnh hưởng; đã xác nhận `VerifierAgent(verify_dataset=True)` chạy qua vẫn báo `valid: True` nên không thể dựa vào verifier để phát hiện lỗi này.
- **Bước tiếp theo:** Chờ nhóm thống nhất hướng sửa (sửa `OrderSellerAgent` trả field phẳng, hoặc Coordinator tự "flatten" `entity_ids` trước khi gọi `PolicyAgent`) rồi chạy lại toàn bộ pipeline 50 case để xác nhận `affected_entities` không còn rỗng.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ `input/EC_*.json` và `data/*.csv` đến `output/EC_*.json` như thế nào qua các agent?
2. Vì sao README yêu cầu evidence ID phải dựng trực tiếp được từ CSV, không cho phép LLM tự suy diễn ID?
3. Ngoài `VerifierAgent`, có bước kiểm tra độc lập nào khác trong luồng xử lý, và nó có đủ để bắt mọi lỗi contract không?
4. Vì sao Policy Agent phải áp dụng đúng thứ tự ưu tiên 6 rule (canceled > unavailable > late_seller > late_logistics > split payment > unsupported claim) thay vì để mỗi agent tự quyết định issue?
5. Một case được coi là xử lý đúng dựa trên artifact và tiêu chí nào?

**Câu trả lời:**

1. `input/EC_*.json` chỉ chứa lời khiếu nại của khách (`customer_request.message`) và một con trỏ `claimed_order_id` — không chứa sự thật nghiệp vụ nào. Coordinator dùng `claimed_order_id` này gọi lần lượt Order & Seller Agent, Payment Agent, Delivery Agent — mỗi agent tự tra cứu vào đúng file CSV thuộc domain của mình trong `data/` (đã được index một lần khi khởi tạo, không đọc lại theo từng case) để lấy facts có thể kiểm chứng. Facts từ 3 agent này được Coordinator gom lại đưa vào Policy Agent để ra `primary_issue`/refund/action, rồi Verifier Agent kiểm tra độc lập trước khi Coordinator ghi ra `output/EC_xxx.json` đúng schema của đề bài.
2. Vì Olist không có refund ledger, tracking checkpoint theo item hay bằng chứng giao sai/giao thiếu — nếu để LLM tự suy diễn ID (ví dụ tự bịa mã tracking), evidence đó không tồn tại trong CSV và bị tính là false positive theo đúng luật chấm điểm ở README mục 5. Ràng buộc evidence ID phải dựng được trực tiếp từ dữ liệu (`order:`, `item:`, `payment:`, `seller:`, `policy:`) buộc mọi kết luận phải truy ngược được về nguồn dữ liệu thật, không phải suy luận ngôn ngữ tự nhiên.
3. Hiện tại chỉ có `VerifierAgent` là bước kiểm tra độc lập trước khi ghi output — nó kiểm tra schema, giới hạn số phần tử, format/tồn tại của evidence ID trong CSV, và tính nhất quán giữa issue/root cause/party/refund/action. Nhưng nó **không đủ**: như phát hiện ở mục 6, verifier không kiểm tra một list ID có đang bị rỗng bất thường hay không, nên một lỗi contract khiến `affected_entities` rỗng vẫn lọt qua với `valid: True`.
4. Vì các rule có phụ thuộc ưu tiên rõ ràng và có thể trùng điều kiện: một order `canceled` vẫn có thể có ≥2 payment row khớp tiền (thoả cả điều kiện `valid_split_payment`), nhưng theo README, rule `canceled_order_paid` phải thắng vì nó đứng trước trong bảng ưu tiên. Nếu để từng agent tự quyết định issue theo dữ liệu domain của riêng mình, không có agent nào nhìn thấy đủ bức tranh để phân xử đúng — bắt buộc phải có một Policy Agent tập trung áp rule theo đúng thứ tự cố định, chỉ dựa trên facts đã được các agent domain xác minh, không tự bịa fact mới.
5. Theo README mục 8, một case đúng phải khớp đồng thời 6 tiêu chí có trọng số: `primary_issue`/`confidence` (20%), `affected_entities` (20%), root cause & responsible parties (15%), evidence IDs (15%), financial resolution (20%), resolution actions (10%) — và quan trọng hơn, nếu bị "hard gate" (ví dụ evidence giả, sai schema) thì case đó nhận 0 điểm bất kể các phần khác đúng đến đâu. Vì vậy một case "xử lý thành công" không chỉ cần `PolicyAgent` ra đúng issue, mà output cuối cùng ghi ra `output/EC_xxx.json` phải được `VerifierAgent` xác nhận hợp lệ trên toàn bộ các tiêu chí này.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Trung Hiếu
**Ngày xác nhận:** 2026-08-05
