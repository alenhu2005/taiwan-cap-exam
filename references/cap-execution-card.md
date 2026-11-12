# 會考出卷執行卡（先讀這一頁）

只讀這頁、`references/current-cap-form.md` 與當科輸出；其他參考文件等工具訊息點名時再查。
科目鍵一律加前綴：`會考國文／會考英語／會考數學／會考社會／會考自然／會考寫作測驗`。

## 指令順序

```text
1  python scripts/prepare_hosted_run.py --subject 會考社會 --run-dir RUN --paper-id ID
2  python scripts/cap_plan.py plan --subject 會考社會 --paper-id ID --level 會考 --output RUN/plan.json
   填 metadata.difficulty_balance_plan.target_counts → python scripts/cap_plan.py check RUN/plan.json
3  每題：python scripts/cap_plan.py item --subject 會考社會 --number N --level 會考   （骨架＋field_guide 欄位格式）
   更快：用 field_guide 的精簡欄位寫一批，python scripts/cap_plan.py expand --plan RUN/plan.json
   --compact items.json --run-dir RUN --output BATCH.json 自動補齊 id、分節、標籤、雜湊與題組繼承
   寫題時就填 est_p（預估通過率）：存檔會回報目前平均是否落在所選難度區間，偏了立刻調整
   宣稱是真實資料的數據（寫出年份、調查、統計、公布者）一律上網查證並填 data_sources（url、retrieved_at）；
   數學與自然可用「某國」「某商店」「某生實驗」這類假設數字，就不必附來源（官方也這樣寫）
   純數值選項由小到大排：expand 會自動排序並同步改答案、誘答與詳解裡的 (A)～(D)；要保留原順序加 keep_order
   畫圖：python scripts/cap_draw.py render 圖.json 圖.pdf --font RUN/fonts/TW-Sung-98_1.ttf
   （座標格線、坐標軸、點、線段、多邊形、圓、弧、角與直角記號、等長記號、中文標籤；點名自動斜體、
   標籤自動避開線條；四張圖當選項用 cap_draw.py options）
   圖檔：python scripts/cap_figure.py subset 圖.pdf --output 圖-小.pdf（只留用到的字形）
   每個題位已排好單元（slot.unit，自然是 domain）：照官方 113–115 的單元分布抽出，題位之間可互換，
   但整卷要留在 plan 的 unit_coverage 範圍內；國文、英語的題組整組同一單元，英語最後一組是克漏字
   數學題位另有 suggested_form（直接作答、判斷兩人看法、推理關係、選出算式、讀新資訊建模、判讀圖表）：
   它只說學生要做什麼，情境與問法由你設計；第 1–3 題直接作答，不包情境
   題材照藍圖的 suggested_focus 走：每次 plan 都抽新的 variety_seed，續做同一份卷時用 --seed 沿用
   範例只示範手法：不要沿用說明文件或過去卷子的情境、地點、材料
   照片：python scripts/web_image.py search "關鍵字"（中英文都試，--offset 換一批）→ web_image.py use
   先找圖再出題、或先出題再找圖都可以；題目必須依圖中真的看得到的證據作答，對不上就改題目
   網路可用時照片必須全部新找；內附圖片庫只在網路不通時備援，並告訴使用者
4  每 2–4 題：python scripts/append_items.py --run-dir RUN --batch BATCH.json [--plan RUN/plan.json 第一批]
   回報的 subject_gate_pending 先修完再寫下一批；--replace 修同一批
   之後改了 plan.json（例如補 target_counts）就在下一批再加 --plan，metadata 會更新（回報 plan_updated）
5  每 2–3 批：python scripts/run_hosted_workflow.py status --state RUN/run-state.json
   → 開新對話，只讀 RUN/NEXT.md、本卡與 current-cap-form.md 接著做
6  全部存完後只要反覆執行：python scripts/run_hosted_workflow.py advance --state RUN/run-state.json
   它依序自動跑完檢查圖表、兩份機械性審查、審查草稿、登錄、鎖定內容、specs、分頁、組成兩本 PDF，
   只在需要你動手時停下並說明要做什麼（補審查、修圖、調版面）；做完再執行 advance
7  組好後：看它列出的頁面與題目 → record-review → auto-review --gates template_composition answer_separation
   → checkpoint → finalize（advance 的 todo 會給完整指令）
   auto-review 另寫出 difficulty.draft.json：每題欄位、錨點鍵（選擇題 objective、非選擇題 constructed-response）、
   官方同題位通過率與你的預估都已填好；逐題蓋答案重做、改預估、填 observations 與 answer_recheck、
   status 改 pass、刪掉 draft_note，存成 difficulty.json
```

## 每題必填（存檔就會檢查）

- 選項標籤 `A`～`D`（不要寫括號）；`final_answer` 為其中之一
- `item_spec.curriculum_codes`：國中第四學習階段代碼；`textbook_volumes`：如 `["第三冊"]`（數學可空）
- `item_spec.cap_competency`：`context_type`、`process`、`real_world_anchor`、`evidence_link`、
  `prerequisite_knowledge`、`hidden_concept`（學生要推出、題幹不可出現的概念）、社會 `domain`／`domains`、
  混合考點寫 `bridge`
- `item_spec.cap_distractors`：每個錯誤選項 `misconception`、`peer_concept`、`expected_pick_rate`（≥ 0.05）、
  `ruled_out_by`（使它確定錯的課本定義或材料證據；寫不出來就表示可能有疑義，重寫）
- `item_spec.cap_unit`：數學、國文、英語的單元（plan 已排好，expand 自動帶入）；自然用 `cap_competency.domain`
- `difficulty_design.linked_decisions` 至少兩項（英語字彙、文法題與國文語文知識題除外）；
  `answers[].reasoning` 至少 2 步（高／極難 3 步），並逐一點名 (A)～(D)
- 數學非選擇題存成第 26、27 題（印「1.」「2.」，詳解標「非選擇題第1題」）；expand 寫 1、2 也會自動換算
- 審查時每題記錄 `estimated_p`（預估通過率）與 `estimated_d`（預估鑑別度）：鑑別度以 plan 裡同題位的
  官方範圍（official_d_113_115）為錨，難題的官方鑑別度本來就較低，照實估，不要美化

## 已知錯誤與解法

| 訊息或症狀 | 解法 |
| :-- | :-- |
| `the figure or its caption prints the answer` | 圖只放證據（數據、地圖、史料），結論留給學生推 |
| `extreme wording`、`absolute words` | 誘答改用學生真的會混淆的相鄰概念，不要「一律、只能、連…也」 |
| `run in blocks` | 社會單題照 `cap_plan.py plan` 排的題序穿插三科 |
| `photographs are newly found` | 用 `web_image.py` 換成新找的照片，不要用內附圖片庫 |
| `甲乙丙丁 combinations` | 組合題太多：改成單一答案的推理題，難度放在材料判讀，不靠格式 |
| `figures as options` | 加入以圖為選項的題目：四個選項各是一張圖（compact 的 `images`） |
| `options run long` | 選項縮短（官方中位數 11–13 字），難度放在題幹與材料 |
| `shares … wording runs with official` | 和某題官方試題的情境太像：換成新的情境與材料 |
| `running mean of estimated_p` | 已存題目的預估和它們題位的目標平均差太多，下一批調整（存檔順序不影響） |
| `third of the paper … estimated at` | 前中後段難度不像官方：開頭放易題、題組前放最難的題 |
| `items on 統計` 等單元題數 | 照 plan 的 unit_coverage 增減該單元，或和別的題位互換單元 |
| `options other than a bare number` | 數學選項太多純數字：改問關係、位置、算式、敘述或判斷 |
| `judge others' claims` | 數學至少兩題判斷甲、乙兩人的看法或作法（process 填 評鑑） |
| `rebuild a textbook exercise` | 課本或參考書的老題型太多（梯子滑動、靠牆圍籬、彈力球…）：保留概念，換新情境與問法 |
| `right-triangle family` | 同一組畢氏數（如 6-8-10）出現在三題以上：換數字 |
| `numeric options print in order` | 數值選項由小到大排；用 expand 會自動排 |
| `items are situated` 上限 | 數學情境題太多（官方約三分之一）：改成直接計算、性質或判斷題 |
| `painted content exceeds the body by N pt` | 訊息已指出題號：縮短最寬那行、縮小該題圖表，或把選項改成一行一個 |
| `rare CJK Extension character` | 改用教科書通用字形 |
| 題組引導語印了兩三次 | 材料裡不要自己寫「閱讀下列選文，回答…」 |
| finalize 要求六個時間階段 | 各階段開始時用 `clock --operation resume --phase <階段>` 記錄，不要事後補 |
| 頁面留白超過 0.32 | 用 `plan` 看分頁，調整圖寬（`width_percent`）或選項排法，不要改題目內容湊頁 |

## 省上下文

- 工具輸出很長時導到檔案，只讀狀態與錯誤；不要把整份 JSON 印進對話。
- 審查報告先用 `refresh-evidence` 產生草稿，只改被標記的題目，不要逐題重寫一遍 item_spec。
- 純文字頁由工具檢查；看圖只看有圖表的頁與被標記的題目。
- 五份需人工判斷的審查報告格式見 `templates/cap-review-templates.json`（只有格式，內容自己寫）。
