# DeepSeek 臨摹

## 原作

插畫原作：**京田スズカ**（見 `image.jpg`）

- pixiv：<https://www.pixiv.net/users/3718340>
- X（Twitter）：<https://x.com/suzukannn>
- Bluesky：<https://bsky.app/profile/suzukannn.bsky.social>
- Skeb（委託）：<https://skeb.jp/@suzukannn>
- BOOTH（同人誌）：<https://suzukannn.booth.pm>

這個專案只是拿原作來做「逐筆重繪」的技術實驗，畫作版權屬原作者所有。如果你喜歡這張圖，請直接去追蹤、委託或購買她的作品。

## 先看這個

直接雙擊 **`player.html`** 就會開始播放，不用安裝任何東西，也不用連網。

- 想快轉或跳段：拖底部那條時間軸。拖到 50%，就是剛好畫完一半的筆數。
- 想放大看細節：點畫布，或按 `EXPAND`。
- 想看完整影片：**`painting_process.mp4`**（1920×1080，約 46 MB）。

## 資料夾裡有什麼

| 檔案 | 說明 |
| --- | --- |
| `player.html` | 單檔播放器，原圖和筆觸資料都包在裡面（約 5 MB） |
| `painting_process.mp4` | 錄好的繪畫過程影片 |
| `image.jpg` | 原圖（原作：京田スズカ） |
| `strokes.json` | 全部筆觸資料：每一筆的位置、顏色、粗細、開始時間 |
| `preview_final.png` | 畫完的樣子 |
| `video_contact_sheet.png` | 0% / 20% / 45% / 72% / 100% 五個階段的對照圖 |

其餘的 `.py` / `.js` 是產生上面這些成果的程式，只有想重做一次才需要動它們。

## 大致怎麼做的

1. **看圖** — 程式先讀原圖，把顏色依明暗和飽和度分成 5 組，同時找出邊線，以及臉、眼睛、嘴巴這些要畫細的位置。
2. **打底** — 用 1,705 筆又寬又長的筆觸，順著畫面紋理方向鋪一層底色。刻意不用「模糊的原圖」當底，因為那樣看起來像貼圖，不像畫。
3. **上色** — 依 5 組顏色，從背景到人物，一筆一筆鋪上去。
4. **刻細節** — 頭髮、臉、眼睛、嘴巴、徽章再補上更短更密的筆。
5. **收邊** — 沿著輪廓補深色線條，讓形狀站起來。
6. **播出來** — 把 15 萬筆資料壓縮塞進一個 HTML 檔，用瀏覽器畫布一筆一筆擦出來。
7. **錄影** — 用無頭瀏覽器逐格截圖，再交給 ffmpeg 合成，所以影片流暢度不受電腦當下快慢影響。

## 幾個數字

- 總筆數 **153,276**，最短的一筆不到 2 像素長
- 影片 10,053 格、30fps，共 5 分 35 秒
- 播放器裡 15 萬筆資料壓縮後約 1.4 MB
- 畫完與原圖相比，平均色差約 19.5（滿分 255），肉眼看已相當接近

## 想自己重跑一次

需要 Python（OpenCV、NumPy）、Node.js（Playwright）和 ffmpeg。依序執行：

```bash
python gen_strokes.py        # 分析原圖、產生筆觸
python jitter_fix.py         # 打散補筆的整齊格紋
python underpaint.py         # 加上最前面的粗底筆
python build_player.py       # 打包成 player.html
node record_chunks.js --chunk 1800 --q 14 --jq 95 --out painting_process.mp4
```

## 授權

程式碼可自由參考使用。`image.jpg` 的畫作版權屬原作者 **京田スズカ**（[pixiv](https://www.pixiv.net/users/3718340) / [X](https://x.com/suzukannn)），不在這個授權範圍內，請勿另行散布或用於商業用途。
