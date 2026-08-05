# Báo cáo vai trò cá nhân — Day 9: Multi-Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Trọng Đức |
| MSSV | 01673 |
| Khóa/Lớp | K3 |
| Vai trò chính | Thành viên 4 — Delivery, Policy và Verifier Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Delivery Agent | `src/agents/delivery_agent.py` — `DeliveryAgent.run` | Order facts và item facts từ Order & Seller Agent | Trạng thái giao trễ, seller handoff trễ, seller vi phạm và bên gây chậm | Hoàn thành |
| Policy Agent | `src/agents/policy_agent.py` — `PolicyAgent.run` | Order facts, payment facts, delivery facts và policy version | Proposal theo output schema gồm issue, root cause, party, refund và action | Hoàn thành |
| Verifier Agent | `src/agents/verifier_agent.py` — `VerifierAgent.run` | Case ID và proposal của Policy Agent | Kết quả `valid` cùng danh sách lỗi có cấu trúc | Hoàn thành |
| Policy constants | `src/policy.py` | Quy tắc `EC_POLICY_V1` trong README | Mapping issue–cause–party–refund–action dùng chung | Hoàn thành |
| Unit test Role 4 | `tests/test_role4_agents.py` | Fixtures đại diện các nhánh policy | 8 test kiểm tra delivery, priority, refund, evidence và verifier | Hoàn thành |

Tôi sở hữu phần phân tích giao hàng, áp dụng chính sách và kiểm tra độc lập kết quả. Tôi không sở hữu bước đọc input, load toàn bộ order/payment CSV, orchestration cuối hoặc ghi 50 output.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Thiết kế contract A2A | Coordinator, Order & Seller Agent, Payment Agent | Agent nhận/trả dictionary có `case_id`, `status`, `facts`, entity/evidence và `errors` |
| Kiểm tra tích hợp Role 2 | Order & Seller Agent | Chạy thành công `EC_002`, `EC_010`, `EC_050`; phát hiện cần thống nhất vị trí `entity_ids` trước khi ghép Coordinator |
| Cấu hình LLM dùng chung | Supervisor | Bổ sung cấu hình OpenRouter với model `qwen/qwen3-8b` 8.2B, không đưa API key vào source |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Phân loại nguyên nhân giao trễ | `DeliveryAgent.run` | Phân biệt seller handoff trễ và logistics giao trễ bằng timestamp CSV | `python3 -m unittest tests.test_role4_agents.DeliveryAgentTests -v` |
| Áp dụng `EC_POLICY_V1` | `PolicyAgent.run`, `src/policy.py` | Hỗ trợ đủ 6 issue theo đúng thứ tự ưu tiên | `python3 -m unittest tests.test_role4_agents.PolicyAgentTests -v` |
| Tính phương án tài chính | `PolicyAgent.run` | Full refund theo payment, refund freight hoặc 0 BRL tùy rule | Các test priority, late seller và split payment |
| Xác minh output độc lập | `VerifierAgent.run`, `EvidenceIndex` | Kiểm tra schema, limit, policy consistency, money và evidence tồn tại trong CSV | `python3 -m unittest tests.test_role4_agents.VerifierAgentTests -v` |
| Đưa code lên repo nhóm | Commit `4c46290` | 8 file, 688 dòng được push lên `main` | `git show --stat 4c46290` |

Một artifact cụ thể là proposal của `PolicyAgent`. Với tình huống giao sau estimated date và carrier nhận hàng sau `shipping_limit_date`, agent tạo:

```json
{
  "assessment": {
    "primary_issue": "late_delivery_seller",
    "case_status": "action_required",
    "confidence": 1.0
  },
  "root_cause_analysis": {
    "ranked_causes": [
      {"cause_code": "SELLER_HANDOFF_AFTER_LIMIT", "rank": 1}
    ]
  },
  "financial_resolution": {
    "currency": "BRL",
    "recommended_refund_brl": 15.0
  },
  "resolution_actions": ["refund_freight"]
}
```

Proposal chỉ được Coordinator ghi ra file sau khi `VerifierAgent` trả `valid: true`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi biến các facts đã được truy xuất thành quyết định nghiệp vụ có thể kiểm chứng. Cùng một phản ánh giao trễ có thể do seller, logistics hoặc không đúng với dữ liệu. Ngoài ra, canceled/unavailable order và split payment có thể cùng xuất hiện với các dấu hiệu khác nên phải áp dụng policy đúng thứ tự ưu tiên. Output cuối còn phải bảo đảm refund, responsible party, action và evidence nhất quán.

### Cách triển khai

`DeliveryAgent` parse timestamp bằng `datetime.fromisoformat`. Agent so sánh `order_delivered_customer_date` với `order_estimated_delivery_date` để xác định khách nhận trễ. Sau đó, với từng item, agent so sánh `order_delivered_carrier_date` với `shipping_limit_date`. Nếu đơn giao trễ và có ít nhất một item được carrier nhận sau hạn thì trách nhiệm thuộc seller; nếu seller bàn giao đúng hạn thì trách nhiệm thuộc logistics.

`PolicyAgent` áp dụng rule theo thứ tự:

1. `canceled_order_paid`.
2. `unavailable_order_paid`.
3. `late_delivery_seller`.
4. `late_delivery_logistics`.
5. `valid_split_payment`.
6. `unsupported_late_claim`.

Tiền được chuyển sang `Decimal`, làm tròn theo `0.01`, sau đó mới đưa vào output. Refund của canceled/unavailable bằng tổng payment; refund của late delivery bằng tổng freight; hai trường hợp không cần hành động tài chính có refund bằng 0.

`VerifierAgent` không sửa proposal. Agent tạo danh sách lỗi có mã, field, expected và actual để Coordinator xử lý. Verifier kiểm tra các giới hạn schema, confidence, currency, refund, case status, root cause, responsible party, action và evidence ID. `EvidenceIndex` load ID thật từ orders, order items, payments và sellers CSV để từ chối evidence không tồn tại.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input Delivery Agent | `case_id`, `order_facts`, danh sách item có `seller_id` và `shipping_limit_date` |
| Output Delivery Agent | Envelope gồm `agent`, `case_id`, `status`, `facts`, `errors` |
| Input Policy Agent | `case_id`, `policy_version`, `order_facts`, `payment_facts`, `delivery_facts` |
| Output Policy Agent | Envelope có `proposal` theo output schema hoặc lỗi `POLICY_NOT_APPLICABLE` |
| Input Verifier Agent | `case_id` và `proposal` |
| Output Verifier Agent | `valid`, `status` và danh sách `errors` có cấu trúc |
| Module phụ thuộc | `src/policy.py`, CSV trong `data/`, facts của Role 2 và Payment Agent |
| Module sử dụng output | Supervisor/Coordinator và output writer |
| Điều kiện lỗi cần xử lý | Timestamp sai, policy version không hỗ trợ, facts không khớp rule, seller issue thiếu seller ID, evidence giả, refund/action/party sai |

### Cách xác minh

```bash
python3 -m unittest discover -v
python3 -m compileall -q src tests
git diff --check
```

- **Kết quả mong đợi:** Tất cả test pass, source compile thành công và không có lỗi whitespace.
- **Kết quả thực tế của commit Role 4:** 8/8 test trong `tests/test_role4_agents.py` pass.
- **Kết quả sau khi tích hợp Role 2 và cấu hình OpenRouter:** toàn repo chạy 14 test và đều pass.
- **Artifact:** `src/agents/delivery_agent.py`, `src/agents/policy_agent.py`, `src/agents/verifier_agent.py`, `tests/test_role4_agents.py`, commit `4c46290`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn giữa để LLM đọc facts và tự quyết định issue/refund, hoặc mã hóa policy bằng code deterministic.
- **Các phương án đã cân nhắc:** (1) đưa toàn bộ facts vào prompt để LLM sinh JSON; (2) dùng Python deterministic cho timestamp, tiền, policy và verifier; LLM chỉ phục vụ Supervisor/handoff.
- **Phương án đã chọn:** Dùng Python deterministic cho cả ba agent thuộc Role 4.
- **Lý do:** Quy tắc đề bài cố định, phép tính tiền và evidence cần lặp lại chính xác. LLM có nguy cơ chọn sai priority, sinh evidence không tồn tại hoặc trả JSON không ổn định. Thiết kế deterministic dễ test, ít tốn token và cho cùng kết quả ở mọi lần chạy.
- **Bằng chứng quyết định phù hợp:** Test `test_canceled_has_priority_over_split_payment` chứng minh canceled được ưu tiên dù có hai payment row; test verifier phát hiện đồng thời refund sai và evidence không hợp lệ.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Khi Policy Agent nhận response theo contract A2A, domain data nằm trong `facts` nhưng `evidence_ids` và entity IDs nằm ở response envelope. Hàm unwrap ban đầu chỉ lấy `facts`, làm mất evidence khi tạo proposal.
- **Bước tái hiện:** Truyền `order_facts={"status": "success", "facts": {...}, "evidence_ids": [...]}` và payment response tương tự vào `PolicyAgent.run`.
- **Nguyên nhân gốc:** Hàm `_facts` thay toàn bộ envelope bằng `envelope["facts"]` mà không gộp metadata cần thiết.
- **Cách xử lý:** Sửa `_facts` để copy domain facts rồi gộp `order_ids`, `item_ids`, `seller_ids`, `payment_ids` và `evidence_ids` từ envelope nếu có.
- **Cách xác minh sau khi sửa:** Test `test_preserves_envelope_entities_and_evidence` kiểm tra order/payment evidence vẫn xuất hiện trong proposal; toàn bộ 8 test Role 4 pass.
- **Điều học được:** Contract A2A phải quy định không chỉ tên field mà cả vị trí field. Integration test dùng response envelope thật cần được viết sớm, không chỉ test dictionary facts rút gọn.

Blocker tích hợp còn cần nhóm thống nhất: Role 2 hiện trả entity dưới `entity_ids`, trong khi một số consumer cũ đọc entity fields trực tiếp ở envelope. Trước khi chạy 50 case, Coordinator hoặc contract chung phải chuẩn hóa cấu trúc này và có integration test.

## 7. Hiểu biết về luồng end-to-end

### 7.1 Dữ liệu đi qua hệ thống như thế nào?

Coordinator đọc từng `input/EC_*.json`, lấy `case_id`, `claimed_order_id` và `policy_version`. Order & Seller Agent truy xuất order/item/seller. Payment Agent truy xuất payment và đối soát với item + freight. Delivery Agent phân tích timestamp. Policy Agent nhận facts đã chuẩn hóa để tạo proposal. Verifier Agent kiểm tra lại proposal với policy và dữ liệu CSV. Chỉ proposal hợp lệ mới được ghi thành `output/EC_*.json`; các handoff được ghi vào `logging/trace.jsonl`.

### 7.2 Vì sao không tin hoàn toàn vào nội dung khiếu nại?

Nội dung khách hàng chỉ là claim. Quyết định phải dựa trên order status, ngày giao thực tế, estimated date, shipping limit, item, seller và payment trong CSV. Ví dụ khách báo giao trễ nhưng `order_delivered_customer_date <= order_estimated_delivery_date` và payment khớp thì kết quả phải là `unsupported_late_claim`.

### 7.3 Vì sao policy phải có thứ tự ưu tiên?

Một order có thể thỏa nhiều dấu hiệu. Ví dụ canceled order có thể có nhiều payment row. Nếu kiểm tra split payment trước thì hệ thống sẽ giải thích payment thay vì hoàn toàn bộ tiền. Vì vậy canceled và unavailable phải được xét trước delivery và split payment.

### 7.4 Evidence được tạo và xác minh như thế nào?

Chỉ dùng năm dạng evidence được đề cho phép: `order:`, `item:`, `payment:`, `seller:` và `policy:`. Order/item/payment/seller evidence phải tồn tại trong CSV; policy evidence phải thuộc tập root-cause code của `EC_POLICY_V1`. Evidence không có trong dataset, như tracking checkpoint hoặc refund transaction, bị từ chối.

### 7.5 Khi nào một case được xem là hoàn thành?

Case hoàn thành khi output đúng schema; issue, confidence, entity, cause, party, evidence, money và action nhất quán; refund làm tròn hai chữ số; không vượt giới hạn số phần tử; Verifier trả `valid: true`; file output có tên trùng input. Toàn bài hoàn thành khi có đúng 50 JSON và trace/metadata của lượt chạy mới nhất.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Trọng Đức

**Ngày xác nhận:** 2026-08-05
