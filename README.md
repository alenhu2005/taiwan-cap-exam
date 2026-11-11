# Taiwan CAP Exam

**用 AI 出一份原創的國中教育會考模擬試題：題本 PDF ＋ 答案詳解 PDF。**

品質目標是**超過正式會考**：每個能量測的指標（鑑別度、誘答品質、選項均衡、情境比例、轉譯型題幹）
都以 113–115 年正式試題為基準，門檻設在官方最好表現之上；出題 AI 每存一批題目就會被檢查，不合格就要重寫。

[下載 Skill ZIP](https://github.com/alenhu2005/taiwan-cap-exam/releases/latest) ·
[會考卷型與品質規範](references/current-cap-form.md) ·
[出卷 AI 執行卡](references/cap-execution-card.md)

## 支援科目

| 科目 | 題型 | 時間 | 依據 |
| :-- | :-- | --: | :-- |
| 國文 | 42 題單選（單題＋題組） | 70 分 | 113–115 正式題本 |
| 英語（閱讀） | 43 題單選（單題＋題組） | 60 分 | 同上；**聽力需要音檔，不製作** |
| 數學 | 25 題單選＋2 題非選（0–3 級分） | 80 分 | 同上，附參考公式頁 |
| 社會 | 54 題單選（單題＋題組），歷史／地理／公民穿插 | 70 分 | 同上 |
| 自然 | 50 題單選（單題＋題組） | 70 分 | 同上 |
| 寫作測驗 | 1 題引導寫作（一至六級分） | 50 分 | 同上 |

## 怎麼用

1. 到 [Releases](https://github.com/alenhu2005/taiwan-cap-exam/releases/latest) 下載 Skill ZIP，**不要解壓縮**。
2. Claude：**Customize → Skills → ＋ → Create skill → Upload a skill**，選 ZIP 後儲存並啟用；
   並在 Settings → Capabilities 打開 *Code execution and file creation*。
   ChatGPT（有 Skills 的帳號）：**Plugins → Skills → Create → Upload from your computer**。
3. 開新對話，選取 `taiwan-exam-generator`，貼上出卷文字：

```text
請用 taiwan-exam-generator 出一份會考社會模擬考，難度：高，交付題本 PDF 與答案詳解 PDF。
```

交付檔名：`會考_社會_{編號}_題本.pdf`、`會考_社會_{編號}_詳解.pdf`。

## 難度可以自己選

在出卷文字寫「難度：低（會考）／中／高／極難」，不寫就是會考難度。越難，全卷平均預估通過率越低
（例：自然 會考 0.54–0.65、中 0.44–0.54、高 0.34–0.44、極難 0.21–0.34）。

**不論哪一級都不超出國中課綱**：每題只能用 108 課綱第四學習階段的內容，必須能用學過的知識一步步推出；
詳解寫出完整推導（高、極難至少三步），逐一說明每個誘答錯在哪裡，並標註**課綱代碼與可能出處冊別**
（例：「課綱：歷Ha-IV-1；可能出處：第三冊（八上）」）。

## 品質關卡（存題時自動檢查）

| 檢查 | 官方 113–115 實測 | 本專案門檻 |
| :-- | :-- | :-- |
| 題幹、材料或圖表透露正解字句 | 0 題 | 0 題 |
| 誘答使用極端字（歸零、廢除、宣告獨立…） | 496 個選項中 0 個 | 0 個 |
| 只有誘答使用絕對化字眼（一律、只能、連…也） | 每年 2–4 題 | ≤ 5% |
| 正解是唯一最長選項 | 0–7% | ≤ 5% |
| 全卷平均鑑別度（審題預估） | 各科 0.47–0.60 | ≥ 官方最好的一年 |
| 鑑別度 < 0.30 的題目 | 0–8% | ≤ 3% |
| 社會單題科別排列 | 1–5 題一段交替 | 連續同科 ≤ 7、換科 ≥ 10 |
| 混合考點（跨科或跨主軸） | — | ≥ 20% |
| 真實情境題 | — | 國文 50%、英數 60%、社自 70% |
| 社會轉譯型題幹（學生自己推出概念） | — | ≥ 60% |

另外也擋下：甲乙丙丁組合題過多（社會 ≤ 3）、選項過長（官方中位數 11–13 字）、缺少以圖為選項的題目、
印出數據卻沒附查證來源、與官方 113–115 試題情境高度重疊（以雜湊指紋比對）、網路可用卻沿用內附圖片庫的照片、數數題、純算術題、自己打的題組引導語、高中課綱代碼、罕用擴充字、
沒有寫出誘答「為什麼確定錯」的題目。每個誘答都要記錄它對應的迷思、借用的相鄰真實概念，
以及預估有多少考生會選。

> 這些門檻是結構檢查，通過不代表品質自動合格；鑑別度、通過率是出題時的**預估**，
> 不是實測。正式使用前仍建議由老師審閱。

## 給出題 AI 的工具

讓 AI 專注在設計題目，機械性的工作交給工具。說明文件只寫原則、不放題目範例，避免 AI 照範例出題；
每次產生藍圖都抽新的題材方向，照片全部上網新找，同一個要求重複生成會得到不同的卷子。

| 指令 | 用途 |
| :-- | :-- |
| `scripts/cap_plan.py plan` | 依官方 115 結構產生命題藍圖：分節、題組位置、社會題序、每題目標通過率，並依卷號分配題材方向（重複生成內容不同） |
| `scripts/cap_plan.py expand` | 精簡寫法自動展開成完整欄位（id、分節、標籤、雜湊、題組繼承） |
| `scripts/cap_figure.py subset` | 圖檔字型子集化（35 MB → 11 KB），附下標與標籤白邊寫法 |
| `scripts/web_image.py` | 上網（維基共享資源）找新照片，自動記錄來源、作者、授權；網路可用時照片必須全部新找 |
| `scripts/cap_plan.py item` | 單題骨架，所有必填欄位都列好 |
| `scripts/append_items.py` | 每 2–4 題存一次，當場回報品質問題 |
| `run_hosted_workflow.py advance` | 預設工作流：題目存完後反覆執行，自動跑完檢查、審查草稿、鎖定、分頁、組卷，只在需要動手時停下 |
| `run_hosted_workflow.py status` | 幾行進度摘要並寫 `NEXT.md`，可換新對話接續、節省上下文 |
| `run_hosted_workflow.py auto-review` | 實際執行檢查，自動寫好四份機械性審查報告 |

## 版面

會考固定版型（封面、頁碼、「請翻頁繼續作答」、數學參考公式頁）依 115 年正式題本量測；
正式題本為 595 × 822 pt，本專案改為 **A4**，方便一般印表機列印。生成卷標示 `Taiwan Exam 模擬試題`，
不冒充國中教育會考正式試題。

## 開發

```sh
python -m pip install -r requirements-test.txt
python -m pytest -q
```

- 重建會考版型：`python scripts/render_cap_template_assets.py --build-all --kai-font TW-Kai-98_1.ttf --sung-font TW-Sung-98_1.ttf`
- 重建官方校準資料：`python scripts/build_cap_pack.py --source-dir <官方題本與統計表資料夾>`
  （官方題本與統計表從 [國中教育會考網站](https://cap.rcpet.edu.tw/examination.html) 下載，不放進本專案）
- 打包 Skill ZIP：`python scripts/build_hosted_skill.py --version <版本> --output <檔名>.zip`

本專案同時保留學測出卷功能；本 README 只說明會考部分。

## 授權

MIT License，見 [LICENSE](LICENSE)。本專案改作自 [niansia/taiwan-exam](https://github.com/niansia/taiwan-exam)（MIT），
原作者版權與出處聲明保留於 LICENSE、[NOTICE](NOTICE) 與 ORIGIN.json；會考試題與統計資料之權利屬國立臺灣師範大學
心理與教育測驗研究發展中心，本專案僅收錄彙總數據與文件雜湊值。
