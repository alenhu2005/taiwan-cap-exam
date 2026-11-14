# 會考出題常用的官方資料入口（只列網址，不存數字）

數據每年更新，所以這裡**不寫任何數字**，只列各主題的官方入口，出題時當場查最新一年的資料，並把
網址與查詢日期記在 `item_spec.data_sources`（`web_image.py use` 與 `cap_plan.py save` 都接受這個欄位）。
連得到與否依執行環境而定；連不到就換同主題的另一個入口，或改用「某國」「某地」的假設數字（數學、自然可以，
社會的統計須查證）。

| 主題 | 入口 |
| :-- | :-- |
| 總體統計、物價、薪資、家庭收支 | 行政院主計總處 統計資訊網 https://www.stat.gov.tw/ |
| 人口推估、少子高齡 | 國家發展委員會 人口推估查詢系統 https://pop-proj.ndc.gov.tw/ |
| 戶籍人口、內政統計 | 內政部 https://www.moi.gov.tw/ （統計專區） |
| 勞動、薪資、外籍勞工 | 勞動部 勞動統計查詢網 https://statfy.mol.gov.tw/ |
| 氣象、氣候觀測 | 交通部中央氣象署 https://www.cwa.gov.tw/ ；氣候觀測資料查詢 https://codis.cwa.gov.tw/ |
| 地震 | 中央氣象署地震測報中心（同上）；美國地質調查所 https://earthquake.usgs.gov/ |
| 水庫、河川、水資源 | 經濟部水利署 https://www.wra.gov.tw/ |
| 空氣品質、廢棄物、環境資料 | 環境部 https://www.moenv.gov.tw/ ；環境資料開放平臺 https://data.moenv.gov.tw/ |
| 能源供需、發電結構 | 經濟部能源署 https://www.moeaea.gov.tw/ |
| 農業生產、農產品 | 農業部 https://www.moa.gov.tw/ ；農業統計資料查詢 https://agrstat.moa.gov.tw/ |
| 交通運輸 | 交通部 統計查詢網 https://stat.motc.gov.tw/ |
| 教育統計 | 教育部統計處 https://depart.moe.edu.tw/ED4500/ |
| 衛生福利 | 衛生福利部統計處 https://dep.mohw.gov.tw/DOS/ |
| 金融、匯率 | 中央銀行 https://www.cbc.gov.tw/ |
| 財政、貿易 | 財政部 https://www.mof.gov.tw/ |
| 法律條文 | 全國法規資料庫 https://law.moj.gov.tw/ ；憲法法庭 https://cons.judicial.gov.tw/ |
| 選舉 | 中央選舉委員會 選舉資料庫 https://db.cec.gov.tw/ |
| 政府開放資料（各機關） | 政府資料開放平臺 https://data.gov.tw/ |
| 臺灣史料、老照片 | 國史館 https://www.drnh.gov.tw/ ；國家文化記憶庫 https://memory.culture.tw/ ；國立臺灣歷史博物館 https://www.nmth.gov.tw/ |
| 古典與公有領域原文 | 維基文庫 https://zh.wikisource.org/ |
| 公有領域與自由授權圖片 | Wikimedia Commons https://commons.wikimedia.org/ （`web_image.py search` 直接查） |
| 衛星影像、地球觀測 | NASA Earth Observatory https://earthobservatory.nasa.gov/ |
| 各國統計 | World Bank Open Data https://data.worldbank.org/ ；UNdata https://data.un.org/ ；FAOSTAT https://www.fao.org/faostat/ ；Our World in Data https://ourworldindata.org/ |

本 Skill 內附的靜態資料：
- 108 課綱國中第四學習階段代碼與條文（含高中階段條目作為超綱對照）：`exam_packs/會考/curriculum/<科>.json`
- 簡化底圖：臺灣 22 縣市（內政部國土測繪中心，政府資料開放授權第 1 版）、東亞與世界國界（Natural Earth，
  公有領域）：`exam_packs/會考/maps/`，用 `cap_draw.py render` 的 `"chart": "map"` 畫。
