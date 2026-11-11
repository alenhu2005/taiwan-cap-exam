# 會考出卷執行卡（先讀這一頁）

只讀這頁、`references/current-cap-form.md` 與當科輸出；其他參考文件等工具訊息點名時再查。
科目鍵一律加前綴：`會考國文／會考英語／會考數學／會考社會／會考自然／會考寫作測驗`。

## 指令順序

```text
1  python scripts/prepare_hosted_run.py --subject 會考社會 --run-dir RUN --paper-id ID
2  python scripts/cap_plan.py plan --subject 會考社會 --paper-id ID --level 會考 --output RUN/plan.json
   填 metadata.difficulty_balance_plan.target_counts → python scripts/cap_plan.py check RUN/plan.json
3  每題：python scripts/cap_plan.py item --subject 會考社會 --number N --level 會考   （骨架，填空）
   題材照藍圖的 suggested_focus 走：每次 plan 都抽新的 variety_seed，續做同一份卷時用 --seed 沿用
   範例只示範手法：不要沿用說明文件或過去卷子的情境、地點、材料
   照片：python scripts/web_image.py search "關鍵字"（中英文都試，--offset 換一批）→ web_image.py use
   先找圖再出題、或先出題再找圖都可以；題目必須依圖中真的看得到的證據作答，對不上就改題目
   網路可用時照片必須全部新找；內附圖片庫只在網路不通時備援，並告訴使用者
4  每 2–4 題：python scripts/append_items.py --run-dir RUN --batch BATCH.json [--plan RUN/plan.json 第一批]
   回報的 subject_gate_pending 先修完再寫下一批；--replace 修同一批
5  每 2–3 批：python scripts/run_hosted_workflow.py status --state RUN/run-state.json
   → 開新對話，只讀 RUN/NEXT.md、本卡與 current-cap-form.md 接著做
6  全部存完後只要反覆執行：python scripts/run_hosted_workflow.py advance --state RUN/run-state.json
   它依序自動跑完檢查圖表、兩份機械性審查、審查草稿、登錄、鎖定內容、specs、分頁、組成兩本 PDF，
   只在需要你動手時停下並說明要做什麼（補審查、修圖、調版面）；做完再執行 advance
7  組好後：看它列出的頁面與題目 → record-review → auto-review --gates template_composition answer_separation
   → checkpoint → finalize（advance 的 todo 會給完整指令）
```

## 每題必填（存檔就會檢查）

- 選項標籤 `A`～`D`（不要寫括號）；`final_answer` 為其中之一
- `item_spec.curriculum_codes`：國中第四學習階段代碼；`textbook_volumes`：如 `["第三冊"]`（數學可空）
- `item_spec.cap_competency`：`context_type`、`process`、`real_world_anchor`、`evidence_link`、
  `prerequisite_knowledge`、`hidden_concept`（學生要推出、題幹不可出現的概念）、社會 `domain`／`domains`、
  混合考點寫 `bridge`
- `item_spec.cap_distractors`：每個錯誤選項 `misconception`、`peer_concept`、`expected_pick_rate`（≥ 0.05）、
  `ruled_out_by`（使它確定錯的課本定義或材料證據；寫不出來就表示可能有疑義，重寫）
- `difficulty_design.linked_decisions` 至少兩項；`answers[].reasoning` 至少 2 步（高／極難 3 步），
  並逐一點名 (A)～(D)
- 審查時每題記錄 `estimated_p`（預估通過率）與 `estimated_d`（預估鑑別度）

## 已知錯誤與解法

| 訊息或症狀 | 解法 |
| :-- | :-- |
| `the figure or its caption prints the answer` | 圖只放證據（數據、地圖、史料），結論留給學生推 |
| `extreme wording`、`absolute words` | 誘答改用學生真的會混淆的相鄰概念，不要「一律、只能、連…也」 |
| `run in blocks` | 社會單題照 `cap_plan.py plan` 排的題序穿插三科 |
| `photographs are newly found` | 用 `web_image.py` 換成新找的照片，不要用內附圖片庫 |
| `painted content exceeds the body by N pt` | 訊息已指出題號：縮短最寬那行、縮小該題圖表，或把選項改成一行一個 |
| `rare CJK Extension character` | 改用教科書通用字形 |
| 題組引導語印了兩三次 | 材料裡不要自己寫「閱讀下列選文，回答…」 |
| finalize 要求六個時間階段 | 各階段開始時用 `clock --operation resume --phase <階段>` 記錄，不要事後補 |
| 頁面留白超過 0.32 | 用 `plan` 看分頁，調整圖寬（`width_percent`）或選項排法，不要改題目內容湊頁 |

## 省上下文

- 工具輸出很長時導到檔案，只讀狀態與錯誤；不要把整份 JSON 印進對話。
- 審查報告先用 `refresh-evidence` 產生草稿，只改被標記的題目，不要逐題重寫一遍 item_spec。
- 純文字頁由工具檢查；看圖只看有圖表的頁與被標記的題目。
