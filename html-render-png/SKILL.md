---
name: html-render-png
description: 把本地 HTML 精确渲染成 PNG 图片（卡片图 / 海报 / 比例图 / 截图交付）。当用户要求「生成一张图 / 卡片图 / 横版图 / 按某页面风格出图 / 精确比例（如 2.35:1、900×383）/ 导出 PNG」且需要文字清晰、版式可控时使用。本机走 Edge 无头模式，无需 playwright node 包。
agent_created: true
---

# HTML → PNG 精确渲染（本机链路）

## 何时用
- 要「一张图」，且图上有**中文文字、精确版式、固定比例**——AI 生图做不到文字准确，必须走 HTML 渲染。
- 常见诉求：卡片图、横版/竖版比例图（2.35:1、16:9）、按某个已有页面的风格出一系列图、报告配图。

## 本机链路（2026-09-25 实测通）
本机**没有** playwright 的 node 包（`ms-playwright/chromium-1234` 有浏览器、但 `playwright-cli/0.1.0/node_modules` 为空），**不要为此装包**——直接用系统 Edge：

```bash
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
"$EDGE" --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 \
  --window-size=900,383 \
  --screenshot="C:\\abs\\path\\out.png" \
  "file:///C:/abs/path/card.html"
```

- `--window-size=W,H` = **视口尺寸**，截图输出 = W×H × device-scale-factor。
- `--force-device-scale-factor=2` 出 2x 高清（900×383 → 1800×766），比例不变、文字锐利。要严格像素尺寸就用 1。
- 批量：`for i in 01 02 03 04; do ...; done`，每张一个 HTML 文件最稳（避免整页切图带来的 Pillow 依赖）。
- 路径：`--screenshot` 用 **Windows 反斜杠绝对路径**，URL 用 `file:///C:/...` 正斜杠；中文路径可正常工作。

## ⚠ 先分清「比例说的是谁」
用户说「比例 900×383」时，**先问清是整图还是单卡**——2026-09-25 出图事故：按单卡 900×383（四张各自 2.35:1）做了，用户要的是**整图** 900×383（四卡压在里面一行排列），全部重排。
- 多卡拼图有两种口径：**① 整图 = n×2.35:1**（长图，如四卡一行 = 8.5:1，卡片保持原尺寸、字号不缩水）；**② 整图严格 2.35:1**（卡片要按比例压进 900 宽，字号随之缩小、文案必须精简）。
- 口径 ② 时卡宽 = `(900 − padding×2 − gap×(n−1)) / n`，本例 n=4、padding 10、gap 8 → 每张 214×363；再按这个宽度反推字号与文案长度，别沿用大卡的字号。

## 版式做法（保证不溢出）
1. `html,body{width:900px;height:383px;overflow:hidden}` + `.card{height:100%;display:flex;flex-direction:column}`，底部块用 `margin-top:auto` 顶到边。
2. **先算高度再写字**：可用高度 = 总高 − 上下 padding；标题区 / 条目区 / 页脚区逐块估行高，宁可留白也别溢出（横版卡片尤其容易在条目文字换行时爆掉）。
3. 渲染完**必须 Read 回 PNG 肉眼验收**（读图即可看溢出、错版、色差），并用 PNG 头字节核尺寸：`b.readUInt32BE(16)+'x'+b.readUInt32BE(20)`（偏移 16/20 是 IHDR 的宽高）。

## ★ 溢出自检：用脚本量，不靠肉眼
当前模型常常**读不了 PNG**（返回「不支持图片」），光靠 Read 图验收会漏掉溢出。改成让页面**自己报**：

```html
<script>
(function () {                              // ← 立即执行 IIFE，不要包在 load 事件里
  var d = document.documentElement, bad = [], info = [];
  document.querySelectorAll('.card').forEach(function (c, i) {
    if (c.scrollHeight > c.clientHeight + 0.5 || c.scrollWidth > c.clientWidth + 0.5) bad.push('c'+(i+1));
  });
  document.querySelectorAll('.card').forEach(function (c, i) {
    var cb = c.getBoundingClientRect(),
        rb = c.querySelector('.rows').getBoundingClientRect(),
        fb = c.querySelector('.foot .in').getBoundingClientRect();
    info.push('c'+(i+1)+':w'+Math.round(cb.width)+'h'+Math.round(cb.height)+'gap'+(fb.top-rb.bottom).toFixed(1));
  });
  document.body.setAttribute('data-check', 'page'+d.scrollWidth+'x'+d.scrollHeight+'|' +
    (bad.length ? bad.join(',') : 'NO-OVERFLOW') + '|' + info.join('|'));
})();
</script>
```

再用 `--dump-dom` 抓回来（**比 Read 图可靠**）：

```bash
"$EDGE" --headless=new --disable-gpu --virtual-time-budget=2000 --window-size=900,700 \
  --dump-dom "file:///C:/abs/x.html" 2>/dev/null | grep -o 'data-check="[^"]*"' | head -1
```

- **⚠️ 别用 `document.title` 传结果**（2026-09-25 实测两次 title 未被改写、抓回来还是原样）。写进 `body` 的 `data-*` 属性最稳；HTML 本身就带同名属性时 `grep` 会先命中源码，用 `<title>CHECK` 这类前缀区分即可。
- 抓取时 `--window-size` 的高度**给大一点**（如 700），避免视口比内容矮、页面被压缩后再测。
- `h` 字段能直接读出**最终整图高度**：单行多卡时 `总高 = 卡高 + padding×2`。
- 顺手量「条目区底 → 底条顶」的间距：四卡这个值**一致**才说明等高且无空隙；某卡偏大＝该卡文字换行更多、把整排撑高了。
- 注意：`.foot` 用 `margin-top:auto` 时会让 `scrollHeight == clientHeight`（SLACK 恒为 0），**不代表没溢出**，要配合间距测量一起看。

## 高度让内容决定（用户说「不用强制比例」时）
用户嫌「高度太空、形状难看」＝固定比例把卡片撑成了瘦长条。此时改成**宽度锁死、高度自适应**：

```css
html,body{width:900px;height:auto}                    /* 不再写死 height */
.wrap{width:900px;padding:14px;display:flex;gap:12px;align-items:stretch}
.card{width:209px;height:auto;display:flex;flex-direction:column}   /* 高度交给内容 */
.rows{flex:1}          /* 或用 .foot{margin-top:auto} 把底条顶到底 */
.foot{margin-top:auto;padding-top:12px}
```

- `.wrap` 的 `align-items:stretch` + `.card{height:auto}` ⇒ **四卡自动等高**（都等于最高那张），不会参差。
- **要让四卡真正齐整，得先控制文字行数一致**：卡宽 209 时内容宽约 183px，经验额度是 **chip ≤ 5 字（约 66px）+ txt ≤ 10 字（约 105px）** 能单行放下；超了就会换行、把那一卡顶高，其余三卡底部出现空白（这正是「形状难看」的第二个来源）。
- 定稿流程：改文案 → 跑自检看 `h`/`gap` → 一致后再截图。`--window-size` 高度就填自检里读到的**总高**，截图正好贴合、不留边。


## 多张卡合成一张长图（一行 / 一列排列）
- **不要缩放卡片**：外层用 flex 容器 + 各卡保持原始固定尺寸（如四张 900×383），字号与单张版完全一致，清晰度不缩水。
- **先算总宽高**：`总宽 = padding×2 + W×n + gap×(n−1)`（四张 900 + gap 28 + padding 28 → 3740）；`总高 = padding×2 + H`。
- 截图时 `--window-size=总宽,总高`，仍带 `--force-device-scale-factor=2` 出高清。
- 合并图里**删掉各卡重复的页脚 meta**（如「900×383」会重复四次，视觉噪音）；卡间距 24~32px、底色比卡面稍深一档（如 `#f6f8fb`）才分得出边界。
- 中间件 HTML（`wide.html`）与单张版共用同一份数据段，改文案两边同步重跑。
- **宽度被锁死但高度自由时**，别硬塞比例——走上面「高度让内容决定」一节，四卡等高、总高由内容定。


## 照已有页面风格出图（复用现有设计 token）
1. **先读目标页面的 `<style>` 取真实 token**——色值（`:root` 变量）、圆角、阴影、字体栈、tag/chip 的 soft 底色与主色配对。不要凭印象配色。
2. 把 token 直接内联进新 HTML（**零外链**，避免渲染时字体/样式没加载上）。
3. 一眼可辨的「家族感」通常来自：`--radius`、`box-shadow` 的两层写法（1px 细边 + 大半径柔影）、顶部 4px 主色条、soft 底 + 主色字的 chip、右上圆角 pill。
4. 本项目常照的基准：示例站点首页 `<PROJECT_ROOT>`（色板：brand `#1b4f8a` / green `#1c7a52` / amber `#b8730a` / violet `#5b4bb5`，bg `#f6f8fb`，线 `#e4e8ef`，圆角 14px）。

## 交付纪律
- 生成器脚本（数据 + 模板）留档，改文案只需改数据、重跑脚本——**不手改 PNG**。
- 文案若是 CCS 按语境代填的示例，交付时**明说「示例文案，可替换」**，不冒充用户口径。
- 产出目录放在项目内（如 `<项目>/<任务名>/`），不要污染既有目录（如 `示例站点/`、`示例站点_publish/`）。
