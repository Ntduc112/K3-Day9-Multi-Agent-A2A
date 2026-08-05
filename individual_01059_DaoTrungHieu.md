# Báo cáo vai trò cá nhân — Day 9: Multi-Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Đào Trung Hiếu |
| MSSV | 01059 |
| Khóa/Lớp | K3 |
| Vai trò chính | (Thành viên 5) Supporting Sub-agents và Integration QA |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Input Validation Agent | `src/agents/input_validation_agent.py` — `InputValidationAgent.run` | Case JSON và policy version | Kết quả hợp lệ/lỗi của input envelope | Hoàn thành |
| Contract Audit Agent | `src/agents/contract_audit_agent.py` — `ContractAuditAgent.run` | Handoff từ Order/Seller, Payment, Delivery | Kiểm tra entity ID, payment ID và field bắt buộc | Hoàn thành |
| Resolution Audit Agent | `src/agents/resolution_audit_agent.py` — `ResolutionAuditAgent.run` | Proposal của Policy Agent | Kiểm tra issue, refund, status và action | Hoàn thành |
| Coordinator integration | `src/coordinator.py` | Case input và response của agent | Handoff động, fallback và trace | Hoàn thành |
| Supporting-agent tests | `tests/test_supporting_agents.py` | Fixture input, envelope và proposal | 7 test cho các nhánh hợp lệ/lỗi | Hoàn thành |

Tôi phụ trách lớp kiểm tra bổ trợ quanh 5 domain agent chính. Các sub-agent này
không tự quyết định refund, không thay thế Policy/Verifier và không suy diễn sự kiện
không có trong CSV.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Module được hỗ trợ | Kết quả |
|---|---|---|
| Chuẩn hóa handoff A2A | `src/coordinator.py`, `src/agents/policy_agent.py` | Giữ được entity/evidence khi response dùng envelope hoặc `facts` |
| Tương thích contract | Order/Seller Agent và Contract Audit Agent | Đọc được entity ID phẳng và dạng `entity_ids` lồng nhau |
| Cập nhật tài liệu | `README.md`, `architecture.md` | Ghi rõ 3 supporting sub-agent và vị trí trong pipeline |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/artifact | Kết quả | Cách xác minh |
|---|---|---|---|
| Kiểm tra input | `InputValidationAgent.run` | Phát hiện thiếu `case_id`, `claimed_order_id` hoặc policy không hỗ trợ | 2 test input validation |
| Kiểm tra contract | `ContractAuditAgent.run` | Phát hiện thiếu facts và payment ID khác order | Test consistent handoff và cross-order payment |
| Tương thích entity envelope | `_payload` trong `contract_audit_agent.py` | Đọc được `entity_ids` lồng nhau | Test legacy nested entity envelope |
| Kiểm tra proposal | `ResolutionAuditAgent.run` | Phát hiện action/status không khớp issue và refund | Test no-action và wrong-action |
| Tích hợp fallback | `Coordinator.run_case` | Ba supporting agent được gọi và ghi trace khi LLM lỗi | Chạy thật `EC_001` offline |

Kết quả kiểm thử hiện tại:

```text
32 passed, 50 subtests passed
```

Case thật `EC_001` đã chạy qua deterministic fallback trong trạng thái LLM offline.
Kết quả là `late_delivery_seller`; trace có handoff của cả ba supporting agent.

## 4. Giải thích kỹ thuật

Pipeline ban đầu đã có Order/Seller, Payment, Delivery, Policy và Verifier Agent,
nhưng còn rủi ro input sai, contract handoff không thống nhất và proposal không nhất
quán trước bước verify dataset.

`InputValidationAgent` kiểm tra cấu trúc case theo input contract của README.
`ContractAuditAgent` chuẩn hóa tạm thời response về payload nội bộ, đọc facts,
entity/evidence ở envelope và cả `entity_ids` lồng nhau. Agent kiểm tra order ID,
payment ID có cùng order hay không và các facts tối thiểu của delivery.

`ResolutionAuditAgent` dùng `ISSUE_RULES` dùng chung với policy để kiểm tra action.
Agent cũng kiểm tra refund không âm và quan hệ giữa refund với `case_status`.

Coordinator gọi input validation trước vòng ReAct. Hai audit còn lại được gọi trước
Verifier trong luồng động hoặc fallback. Nếu LLM kết thúc sớm, Coordinator vẫn bảo
đảm audit bổ trợ được chạy trước khi trả proposal.

### Input, output và contract

| Agent | Input | Output |
|---|---|---|
| `input_validation_agent` | Case JSON | `status`, `facts.input_valid`, `errors` |
| `contract_audit_agent` | `order_facts`, `payment_facts`, `delivery_facts` | `status`, `valid`, structured `errors` |
| `resolution_audit_agent` | Policy `proposal` | `status`, `valid`, structured `errors` |

Các agent này chỉ phát hiện lỗi. Quyết định cuối vẫn thuộc Policy Agent và Verifier
Agent theo đúng kiến trúc README.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Có thể thêm agent đọc review/customer hoặc thêm lớp validation quanh pipeline.
- **Phương án chọn:** Thêm 3 supporting sub-agent validation-only.
- **Lý do:** Sáu rule của bài không sử dụng review/customer để quyết định refund.
  Ngược lại, input schema, evidence/entity ID, tiền, status và action là tiêu chí
  được chấm trực tiếp. Validation agent vì vậy có tác động rõ hơn và ít nguy cơ
  suy diễn dữ liệu ngoài CSV.
- **Bằng chứng:** Test cross-order payment và action sai bị phát hiện; envelope
  `entity_ids` lồng nhau hợp lệ vẫn được chấp nhận.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Contract Audit Agent báo thiếu `order_ids` dù response thật của
  Order/Seller Agent có dữ liệu đúng.
- **Nguyên nhân:** Entity ID nằm trong key lồng `entity_ids`, nhưng audit ban đầu
  chỉ đọc field phẳng hoặc dữ liệu trong `facts`.
- **Cách xử lý:** Bổ sung bước đọc `entity_ids` trong `_payload` và thêm test
  `test_contract_audit_accepts_legacy_nested_entity_envelope`.
- **Cách xác minh:** Chạy `EC_001` qua fallback; audit được gọi và output vẫn có
  `primary_issue = late_delivery_seller`.
- **Điều học được:** A2A contract cần quy định cả vị trí field, không chỉ tên field.
  Integration test phải dùng response envelope thật thay vì chỉ facts rút gọn.

## 7. Hiểu biết về luồng end-to-end

1. Coordinator nhận `input/EC_*.json` và gọi input validation. Order/Seller lấy
   order/item/seller; Payment đối soát payment; Delivery phân tích timestamp;
   Contract Audit kiểm tra handoff; Policy áp dụng sáu rule; Resolution Audit kiểm
   tra proposal; Verifier xác minh schema, evidence, tiền và policy trước khi ghi output.
2. Evidence ID phải dựng trực tiếp từ CSV vì README không cho phép tự tạo tracking
   event, transaction hoặc bằng chứng không tồn tại.
3. Supporting agent không thay thế domain agent; chúng tạo điểm kiểm tra độc lập.
4. Policy vẫn phải ưu tiên canceled, unavailable, delivery, split payment rồi
   unsupported claim. Resolution Audit chỉ kiểm tra, không đổi thứ tự này.
5. Case hoàn thành khi output đúng schema, entity/evidence hợp lệ, tiền và refund
   đúng, action/status nhất quán và Verifier trả `valid`.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Đào Trung Hiếu  
**Ngày xác nhận:** 2026-08-05
