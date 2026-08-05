# Phân công nhóm 4 thành viên — Multi-Agent E-commerce Dispute Resolution

## 1. Mục tiêu chung

Xây dựng hệ thống multi-agent xử lý 50 yêu cầu trong `input/`, đối chiếu dữ liệu Olist trong `data/`, áp dụng `EC_POLICY_V1` và tạo đúng 50 file JSON tương ứng trong `output/`.

Hệ thống cần thể hiện rõ:

- Mỗi agent có vai trò và contract riêng.
- Có handoff dữ liệu giữa các agent.
- Kết luận dựa trên dữ liệu CSV có thể kiểm chứng.
- Có bước kiểm tra độc lập trước khi ghi output.
- Lượt chạy cuối được ghi vào `logging/trace.jsonl` và `logging/metadata.json`.

## 2. Phân công 4 thành viên

| Thành viên | Vai trò chính | Deliverable |
|---|---|---|
| Thành viên 1 | Coordinator và tích hợp | Runner 50 case, A2A handoff, output, trace, metadata |
| Thành viên 2 | Order & Seller Agent | Truy xuất order/item/seller, xác định seller bàn giao trễ |
| Thành viên 3 | Payment Agent | Đối soát payment, item + freight và split payment |
| Thành viên 4 | Delivery, Policy & Verifier Agent | Phân tích giao hàng, áp policy và kiểm tra kết quả |

### Thành viên 1 — Coordinator và Integration

Nhiệm vụ:

- Đọc toàn bộ `input/EC_*.json`.
- Tạo context cho từng case từ `case_id`, `claimed_order_id` và `policy_version`.
- Điều phối lời gọi giữa các agent theo đúng workflow.
- Tổng hợp kết quả thành output schema của đề bài.
- Ghi `output/EC_001.json` đến `output/EC_050.json`.
- Ghi trace handoff vào `logging/trace.jsonl`; mỗi lượt chạy phải ghi mới, không append trace cũ.
- Ghi thông tin model và runtime vào `logging/metadata.json`.
- Tích hợp code của cả nhóm và phụ trách command chạy end-to-end.
- Hoàn thiện phần tổng quan và sơ đồ trong `architecture.md`.

File/module đề xuất:

```text
src/main.py
src/coordinator.py
src/contracts.py
src/trace.py
```

Tiêu chí hoàn thành:

- Chạy được một case và toàn bộ 50 case.
- Một agent lỗi không làm mất thông tin case đang xử lý.
- Tạo đúng 50 file output, tên file khớp input.
- Trace thể hiện được agent gửi, agent nhận và kết quả handoff.

### Thành viên 2 — Order & Seller Agent

Nhiệm vụ:

- Đọc và index các file:
  - `olist_orders_dataset.csv`
  - `olist_order_items_dataset.csv`
  - `olist_sellers_dataset.csv`
- Tìm order bằng `claimed_order_id`.
- Lấy trạng thái đơn, các mốc thời gian, item và seller liên quan.
- Tính `item_total_brl` và `freight_total_brl`.
- Với từng item, so sánh `order_delivered_carrier_date` với `shipping_limit_date`.
- Trả về seller nào bàn giao muộn.
- Tạo entity ID và evidence ID hợp lệ cho order, item và seller.
- Viết unit test cho trường hợp một item, nhiều item, thiếu item và seller giao trễ.

File/module đề xuất:

```text
src/data_store.py
src/agents/order_seller_agent.py
tests/test_order_seller_agent.py
```

Tiêu chí hoàn thành:

- Không đọc lại toàn bộ CSV cho từng case; dữ liệu phải được load/index một lần.
- Tổng item và freight đúng đến hai chữ số thập phân.
- ID sinh ra đúng các định dạng:
  - `order:<order_id>`
  - `item:<order_id>:<order_item_id>`
  - `seller:<seller_id>`

### Thành viên 3 — Payment Agent

Nhiệm vụ:

- Đọc và index `olist_order_payments_dataset.csv` theo `order_id`.
- Lấy toàn bộ payment row của order.
- Tính `payment_total_brl`.
- Nhận `item_total_brl` và `freight_total_brl` qua contract để đối soát.
- Xác định payment khớp nếu sai lệch không quá `0.10 BRL`.
- Xác định `valid_split_payment` khi có từ hai payment row và tổng payment khớp.
- Tạo payment entity/evidence ID.
- Viết unit test cho payment đơn, split payment, lệch tiền và không có payment.

File/module đề xuất:

```text
src/agents/payment_agent.py
src/money.py
tests/test_payment_agent.py
```

Tiêu chí hoàn thành:

- Dùng `Decimal` hoặc cơ chế tiền tệ tương đương; không cộng tiền trực tiếp bằng binary float.
- Không nhân `payment_value` với `payment_installments`.
- Payment ID đúng định dạng `payment:<order_id>:<payment_sequential>`.

### Thành viên 4 — Delivery, Policy và Verifier Agent

Nhiệm vụ Delivery:

- So sánh ngày giao thực tế với ngày giao dự kiến.
- Xác định đơn có giao trễ hay không.
- Nếu giao trễ, dùng kết quả seller handoff để phân biệt trách nhiệm seller và logistics.

Nhiệm vụ Policy:

- Áp dụng sáu rule theo đúng thứ tự ưu tiên.
- Sinh `primary_issue`, `case_status`, root cause, responsible party, refund và action.
- Không tự tạo facts không có trong kết quả của các agent dữ liệu.

Nhiệm vụ Verifier:

- Validate schema và giới hạn số phần tử.
- Kiểm tra entity/evidence ID có tồn tại trong CSV.
- Tính lại các tổng tiền và refund.
- Kiểm tra sự thống nhất giữa issue, root cause, party, refund, status và action.
- Trả lỗi có cấu trúc để Coordinator sửa hoặc dựng lại output.

File/module đề xuất:

```text
src/agents/delivery_agent.py
src/agents/policy_agent.py
src/agents/verifier_agent.py
src/policy.py
tests/test_policy.py
tests/test_verifier.py
```

Tiêu chí hoàn thành:

- Policy luôn áp dụng đúng thứ tự trong README.
- Verifier phát hiện được evidence giả, sai tiền, sai action và sai `case_status`.
- Không cho ghi output cuối nếu verification thất bại.

## 3. Luồng gọi agent

```text
Input JSON
    |
    v
Coordinator
    |
    +--> Order & Seller Agent
    |        |
    |        +--> order_facts + item_facts + seller_facts
    |
    +--> Payment Agent
    |        |
    |        +--> payment_facts + reconciliation
    |
    +--> Delivery Agent
             |
             +--> delivery_facts
                       |
                       v
                  Policy Agent
                       |
                       +--> proposed_resolution
                                  |
                                  v
                            Verifier Agent
                              |       |
                            valid   invalid
                              |       |
                              v       +--> structured feedback về Coordinator
                         Output JSON
```

Order & Seller Agent có thể bắt đầu song song với phần truy xuất payment. Tuy nhiên Payment Agent cần tổng item và freight để hoàn tất reconciliation; Delivery Agent cần các mốc order và `shipping_limit_date`. Policy Agent chỉ được chạy sau khi Coordinator nhận đủ facts.

## 4. Contract trao đổi giữa các agent

Các agent phải trao đổi bằng object/JSON có schema cố định, không truyền kết quả chỉ bằng đoạn văn tự do.

Request cơ bản:

```json
{
  "case_id": "EC_001",
  "order_id": "<olist_order_id>",
  "policy_version": "EC_POLICY_V1"
}
```

Response chung:

```json
{
  "agent": "order_seller_agent",
  "case_id": "EC_001",
  "status": "success",
  "facts": {},
  "evidence_ids": [],
  "errors": []
}
```

Quy tắc contract:

- `status` chỉ nhận `success` hoặc `error`.
- Fact tiền tệ nội bộ nên dùng chuỗi decimal như `"115.00"`.
- Timestamp giữ nguyên giá trị CSV; không tự chuyển múi giờ.
- Agent chỉ trả dữ liệu thuộc domain của mình.
- Không agent nào được tự bịa ID, tracking event, refund transaction hoặc bằng chứng không có trong CSV.
- Mọi thay đổi contract phải được cả nhóm thống nhất trước khi merge.

## 5. Thứ tự áp dụng policy

Policy Agent phải áp dụng đúng thứ tự sau:

1. `canceled_order_paid`
2. `unavailable_order_paid`
3. `late_delivery_seller`
4. `late_delivery_logistics`
5. `valid_split_payment`
6. `unsupported_late_claim`

| Primary issue | Responsible party | Refund | Action |
|---|---|---:|---|
| `canceled_order_paid` | `platform / OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `unavailable_order_paid` | `platform / OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `late_delivery_seller` | Seller vi phạm | Tổng freight | `refund_freight` |
| `late_delivery_logistics` | `logistics_provider / LOGISTICS_PROVIDER` | Tổng freight | `refund_freight` |
| `valid_split_payment` | Không có | 0 | `explain_valid_split_payment` |
| `unsupported_late_claim` | Không có | 0 | `reject_late_refund` |

Lưu ý: một order canceled có nhiều payment row vẫn phải là `canceled_order_paid` vì rule canceled có độ ưu tiên cao hơn split payment.

## 6. LLM, API key và bảo mật

- Có thể dùng một API key chung cho tất cả agent; không cần mỗi agent một key.
- Nếu chạy model local như Ollama thì có thể không cần API key.
- Model của từng agent phải có kích thước không quá 10B parameters.
- Tên model phải khai báo rõ trong source code và `logging/metadata.json`.
- API key/secret phải đặt trong `.env`, tuyệt đối không hard-code hoặc commit.
- Endpoint có thể đặt trong `.env` nếu phụ thuộc môi trường.
- Không đưa `.env`, API key, token hoặc secret vào trace, output hay báo cáo.

Ví dụ:

```env
LLM_API_KEY=replace_me
LLM_BASE_URL=https://provider.example/v1
```

`.gitignore` tối thiểu:

```gitignore
.env
__pycache__/
.pytest_cache/
output.zip
```

LLM nên dùng để điều phối, handoff hoặc diễn giải facts. Việc join CSV, so sánh timestamp, tính tiền, áp policy và verify nên thực hiện bằng code deterministic để bảo đảm kết quả lặp lại được.

## 7. Trace và metadata

Mỗi handoff nên có ít nhất hai event: bắt đầu gọi agent và nhận kết quả. Một dòng trace JSONL mẫu:

```json
{"timestamp":"2026-08-05T10:30:00+07:00","case_id":"EC_001","event":"agent_handoff","from_agent":"coordinator","to_agent":"payment_agent","status":"started"}
```

Không ghi toàn bộ dataset hoặc secret vào trace. `metadata.json` cần khai báo ít nhất:

```json
{
  "model": "<model-id-trong-source-code>",
  "parameter_size": "<=10B",
  "framework": "<framework>",
  "runtime": "<local-or-provider>"
}
```

## 8. Quy trình Git và tích hợp

Branch đề xuất:

```text
feature/coordinator
feature/order-seller-agent
feature/payment-agent
feature/delivery-policy-verifier
```

Thứ tự làm việc:

1. Cả nhóm thống nhất `contracts.py` và output schema.
2. Thành viên 2 và 3 triển khai agent dữ liệu độc lập.
3. Thành viên 4 viết policy/verifier bằng fixture trong khi chờ tích hợp.
4. Thành viên 1 tích hợp, chạy thử từng case rồi chạy đủ 50 case.
5. Cả nhóm review output, trace, metadata và tài liệu.
6. Commit đầy đủ source code trước khi đóng gói bài nộp.

Không commit đè thay đổi của thành viên khác. Mỗi pull request cần ghi rõ file sở hữu, contract thay đổi và lệnh test đã chạy.

## 9. Kiểm thử và tiêu chí hoàn thành

Command mục tiêu:

```bash
pytest
python -m src.main --input-dir input --output-dir output
python -m src.validate_outputs --input-dir input --output-dir output
```

Checklist trước khi nộp:

- [ ] Có source code thể hiện agent, handoff và verifier thật.
- [ ] Tất cả unit/integration test đều pass.
- [ ] `output/` chứa đúng 50 JSON từ `EC_001.json` đến `EC_050.json`.
- [ ] Không có file lạ trong `output/`.
- [ ] Mỗi output đúng schema và giới hạn số phần tử.
- [ ] Entity/evidence ID tồn tại và đúng định dạng.
- [ ] Tổng item, freight, payment và refund đúng hai chữ số thập phân.
- [ ] Policy được áp dụng đúng thứ tự ưu tiên.
- [ ] `case_status` khớp với refund/action.
- [ ] `trace.jsonl` là trace của lượt chạy mới nhất, không append lịch sử cũ.
- [ ] `metadata.json` ghi đúng model, parameter size, framework và runtime.
- [ ] `architecture.md` mô tả vai trò, quyền truy cập và luồng handoff.
- [ ] Báo cáo cá nhân đã thay toàn bộ placeholder và đúng nội dung bài Olist.
- [ ] `.env` và secret không xuất hiện trong Git hoặc file nộp.
- [ ] Source code đã được commit trước khi tạo `output.zip`.

## 10. Các lỗi dễ gặp

- Nhân `payment_value` với `payment_installments`, làm tổng payment sai.
- Dùng `customer_id` như định danh khách hàng xuyên nhiều order thay vì `customer_unique_id`.
- Chọn split payment trước canceled/unavailable do áp sai thứ tự policy.
- So sánh timestamp dưới dạng không thống nhất hoặc tự chuyển timezone không cần thiết.
- Dùng float để cộng tiền và phát sinh sai số.
- Hoàn toàn tin vào nội dung khiếu nại thay vì kiểm tra CSV.
- Tạo evidence như tracking/refund transaction không tồn tại trong dataset.
- Để LLM tự tính tiền hoặc tự suy diễn facts.
- Append trace của nhiều lần chạy vào cùng file.
- Đưa source code, `.env` hoặc logging vào `output.zip`.
- Quên commit 50 input hiện đang ở trạng thái untracked.
- Giữ nguyên phần Crossref/vector index không liên quan trong báo cáo cá nhân mẫu.
