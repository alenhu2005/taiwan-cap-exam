# 會考出卷流程：存檔、排版、審查、交付

會考的預設閱讀路線只有四份：`cap-execution-card.md`（指令順序）、`current-cap-form.md`（共用規則）、
當科說明（`cap-<科>.md`）與本頁。學測的文件（`hosted-execution.md` 等）不用讀；工具訊息點名某份文件時再查。

## 一、寫題：每批一個指令

1. 把 2–4 題寫成精簡格式的陣列（欄位見 `templates/cap-item-templates.json`），存成 `items.json`。
2. `python scripts/cap_plan.py save --plan RUN/plan.json --compact items.json --run-dir RUN`
   它依序完成：檢查（選項字數、絕對化字眼、正解外洩、課綱代碼、選項會不會一行一個）→ 展開成完整欄位 →
   存檔。存檔時同時：
   - 大型圖檔自動精簡字型並更新雜湊（避免 30 MB 的圖拖慢每次組版）；
   - 只檢查這批新加的圖，並在 `RUN/figure-previews/` 輸出每張圖的印刷尺寸預覽，看一眼就好；
   - 在 `RUN/review-book.json` 加入這批題目的審查紀錄；
   - 記錄 checkpoint 與寫題時間（寫題階段 20 分鐘內沒有存檔才算閒置）。
3. 回報裡的 `lint.errors`、`subject_gate_pending`、`figure_check` 先修再寫下一批；修同一批加 `--replace`。
4. **趁題目還熟，填這批題目在 `review-book.json` 的紀錄**（見「三、審查」）。
5. **寫題期間不做 proof。** 只有第一批建議 proof 一次（確認字型與版面）；之後看 `figure-previews/` 的圖即可。
   版面在全部寫完後決定一次，過程中看過的裁切圖會因為最後調版而作廢，等於白看。

每 2–3 批執行 `python scripts/run_hosted_workflow.py status --state RUN/run-state.json`，在新對話只讀
`RUN/NEXT.md`、執行卡與當科說明接著做。

## 二、排版：全部寫完後，plan 一次、build 一次

1. `python scripts/run_hosted_workflow.py check-figures --state RUN/run-state.json`
   （已檢查過且沒改的圖直接沿用結果，只開新的或改過的圖）
2. `python scripts/run_hosted_workflow.py specs --state RUN/run-state.json` → `plan`：看每頁留白與題目落點。
3. 需要調整就寫 `RUN/layout-hints.json` 一次定案，再跑一次 `specs` 與 `plan`：
   `{"items": {"q12": {"columns": 2}, "q31": {"figure_width_pt": 200, "figure_position": "right"}}}`
   常用鍵：`columns`（選項欄數 1／2／4）、`figure_width_pt`、`figure_position`、`keep_with_next`、`split`。
4. `build`：組成兩本 PDF，列出要看的頁面與裁切圖（`review_queue`）。逐張看，寫進 `record-review`。
   數學非選擇題各自一頁，頁面留白是作答空間，不算排版缺陷。

`advance --state RUN/run-state.json` 會自動依序跑完可以機械化的步驟，只在需要你動手時停下。

## 三、審查：每題一筆紀錄，最後一次編譯

`review-book.json` 每題一筆，四段都要填：

| 段落 | 要做的事 | 必填 |
| :-- | :-- | :-- |
| `answer_check` | 蓋住答案重解一次，和存檔答案比對；說明每個誘答確定錯的理由 | `status`、`observations` |
| `originality` | 和官方題目、課本與參考書常見題型、本卷其他題目比較：情境、問法、解法哪裡是新的 | 同上 |
| `visual` | 圖上學生讀得到的證據、灰階可讀、和題幹一致（無圖的題目工具已填 `not_applicable`） | 同上 |
| `difficulty` | 預估通過率與鑑別度（以 plan 的官方同題位範圍為錨）、最短解法、關鍵判斷、找過的捷徑、重解紀錄 | 加上 `estimated_p`、`estimated_d`、`shortest_route`、`decisive_steps`、`shortcut_search`、`answer_recheck` |

`paper` 段寫一次：難度審查的 `review_reason`、`author_context`、`reviewer_context`（單一脈絡時兩者相同），
以及 `source_grounding`（每份材料與數據的來源與核對方式）。

- 題目改過，該題紀錄自動回到 pending，舊紀錄保留在 `previous`；沒改的題目不受排版調整影響，不必重審。
- 全部填完後：`python scripts/run_hosted_workflow.py compile-reviews --state RUN/run-state.json`
  寫出 `answers`、`originality`、`visuals`、`difficulty`、`source_grounding` 五份報告並登錄；
  有缺漏就列出題號與欄位，什麼都不寫。不必再手寫這五份 JSON，也不必用 `refresh-evidence` 重建草稿。
- `auto-review` 產生四份機械性報告（結構、難度分布、模板、答案分離）。

## 四、交付

`checkpoint` → `finalize --state RUN/review-state.json`（`advance` 的 todo 會給完整指令）。`finalize` 會再精簡
兩本 PDF 的字型，交付 `會考_<科>_<paper_id>_題本.pdf` 與 `_詳解.pdf`。

## 環境提醒

- 網路下載的圖片常被擋或回傳 HTML 錯誤頁；用 `web_image.py`（會驗證檔案），或用 `cap_draw.py` 依資料畫圖。
- 執行環境可能在兩次對話之間清掉暫存檔；從 `RUN/NEXT.md` 與存檔狀態重建，不要手改狀態檔。
- 報告裡的 exam 雜湊比目前的舊，最終檢查會拒絕；題目改過就重新 `compile-reviews`。
