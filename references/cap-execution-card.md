# 會考出卷執行卡（先讀這一頁）

只讀這頁、`references/current-cap-form.md`、當科的專屬說明（`cap-chinese.md`／`cap-english.md`／`cap-math.md`／`cap-social.md`／`cap-science.md`／`cap-writing.md`：出題架構、習慣、課綱對照與本科規則）與當科輸出；其他參考文件等工具訊息點名時再查。
科目鍵一律加前綴：`會考國文／會考英語／會考數學／會考社會／會考自然／會考寫作測驗`。

## 指令順序

```text
1  python scripts/prepare_hosted_run.py --subject 會考社會 --run-dir RUN --paper-id ID
2  python scripts/cap_plan.py plan --subject 會考社會 --paper-id ID --level 會考 [--volumes 1-4] --output RUN/plan.json
   --volumes 限定出題冊別（預設 1-6；第一冊＝七上 … 第六冊＝九下），藍圖只排範圍內教過的單元、標題加註冊別
   填 metadata.difficulty_balance_plan.target_counts → python scripts/cap_plan.py check RUN/plan.json
3  寫 2–4 題的精簡紀錄（欄位與合法值：templates/cap-item-templates.json），一個指令存檔：
   python scripts/cap_plan.py save --plan RUN/plan.json --compact items.json --run-dir RUN [--replace]
   它會先檢查（cap_plan.py lint 可以只檢查不存）、展開、存檔，並自動：大圖精簡字型、只檢查這批新圖、
   在 RUN/figure-previews/ 輸出圖的預覽、更新 review-book.json、記 checkpoint 與時間
   回報的 lint.errors、subject_gate_pending、figure_check 先修再寫下一批
4  趁熱填這批題目在 RUN/review-book.json 的審查紀錄（answer_check、originality、visual、difficulty）
   寫題期間不做 proof：只有第一批 proof 一次；圖看 figure-previews/ 就好
5  每 2–3 批：python scripts/run_hosted_workflow.py status --state RUN/run-state.json
   → 開新對話，只讀 RUN/NEXT.md、本卡與當科說明接著做
6  全部存完：check-figures → specs → plan（一次定案 RUN/layout-hints.json）→ build → 看 review_queue → record-review
   （advance --state RUN/run-state.json 會依序自動跑完能機械化的步驟）
7  python scripts/run_hosted_workflow.py compile-reviews --state RUN/run-state.json（五份審查報告一次寫好並登錄）
   → auto-review → checkpoint → finalize
```

詳細流程與審查簿欄位見 `references/cap-workflow.md`。

工具：
- 課綱代碼與條文：`exam_packs/會考/curriculum/<科>.json`（國中第四學習階段；`senior_high` 是高中條目，出現就是超綱）
- 畫圖：`python scripts/cap_draw.py render 圖.json 圖.pdf --font RUN/fonts/TW-Sung-98_1.ttf`
  幾何圖（點線圓角、坐標軸）或 `"chart"`：bar、line、climate（雨溫圖）、pyramid（人口金字塔）、profile（地形剖面）、
  table、card（史料圖卡）、map（臺灣縣市含金馬、東亞、世界；灰階分級填色、指北針）；每張圖附 PNG 預覽
- 找照片：`web_image.py search` → `web_image.py use`（回傳可直接貼上的 compact_figure 與 compact_data_source）
- 數據入口：`references/cap-data-sources.md`（只列官方網址，數字當場查）

## 每題必填（存檔就會檢查）

- 選項標籤 `A`～`D`（不要寫括號）；`final_answer` 為其中之一
- `item_spec.curriculum_codes`：從 `exam_packs/會考/curriculum/<科>.json` 抄國中第四學習階段代碼（不在表裡會被擋）；
  `textbook_volumes`：如 `["第三冊"]`（數學可空；限定冊別時每科都要填）
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
| `not in the 108 課綱 table` | 代碼抄錯：到 `exam_packs/會考/curriculum/<科>.json` 找正確代碼 |
| `outside the paper's range` | 限定冊別的卷子用到範圍外的冊別或年級代碼：換題或換範圍內的概念 |
| `concepts hold … items`（社會） | 七、八、九年級各至少兩成（官方 114–115）：調整幾題的主題年級 |

## 省上下文

- 工具輸出很長時導到檔案，只讀狀態與錯誤；不要把整份 JSON 印進對話。
- 審查寫在 review-book.json（每題一筆），最後 `compile-reviews` 產生五份報告；題目沒改，紀錄就一直有效。
- 純文字頁由工具檢查；看圖只看有圖表的頁與被標記的題目。
- 五份需人工判斷的審查報告格式見 `templates/cap-review-templates.json`（只有格式，內容自己寫）。
