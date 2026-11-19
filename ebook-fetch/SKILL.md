---
name: ebook-fetch
description: 找电子书并落地本地文件的正式能力（两条书源腿：诚通网盘优先、百度 AI 对话小程序兜底）。当需要找书、下载电子书（epub/mobi/azw3/pdf）、测试某个推文/仓库推荐的电子书源能不能用、或给书籍蒸馏流水线补原料时使用本 skill。覆盖：按书名搜诚通索引、一键下载三格式、百度小程序渲染扒 PDF 链、下载后验货（magic/大小/负控）。
agent_created: true
---

# Ebook Fetch — 电子书 sourcing 与落地

## Overview

把「找一个书名 → 本地拿到电子书文件」固化为可复用能力。两条实现腿（2026-10-17 实测固化）：

- **诚通腿**（优先）：GitHub 仓库 `jbiaojerry/ebook-treasure-chest`（20.7k stars、日更）做文本索引，`md/` 下 1000 个分类文件，每本书一条诚通网盘分享链（提取码统一 `8866`），`scripts/ctfile_fetch.py` 纯 HTTP 两步 API 直下 epub/mobi/azw3 三格式；
- **百度腿**（兜底）：百度智能小程序「Ai未来夜校」AI 对话页 JS 渲染，无头浏览器渲染后扒百度网盘 PDF 链，`bdpan download` 落盘。

**裁决（2026-10-17）**：两腿并存、代码不合并（上游/下游/产物全不同，硬合并＝泄漏抽象）；使用顺序＝**诚通优先、百度兜底**（免登录、索引可 grep、三格式、约 1 分钟/本）。

脚本与 SOP 真源均在 368 容器，本 skill 是路由层，不复制代码（避免双真源）。

## 决策树（按顺序走，命中即停）

1. **已有诚通分享链**（形如 `https://url89.ctfile.com/f/31084289-1375498459-018013?p=8866`）→ 直接走腿一；
2. **只有书名**→ 先 curl 诚通索引 grep（腿一步骤 1），有链走腿一；没有→腿二；
3. **腿二也没有**（小程序答「未找到」或 token 过期重试无效）→ 登记缺口，转 PDF 直下渠道（夜雨聆风 / TG 电子书频道 / 4mf.top / 飞鹰目录 / pdfs.top / libgen），细节见 references；
4. 每落地一本，跑一次对应腿的 verify 检查器（红绿）确认链路仍健康。

## 腿一：诚通网盘（优先）

容器路径变量：`CT=<工作目录>`

**步骤 1 · 按书名搜索引**（索引是纯文本 md，curl 可拉，先确认有货再下载）：

```bash
curl -s "https://raw.githubusercontent.com/jbiaojerry/ebook-treasure-chest/main/md/<分类>.md" | grep "<书名关键词>"
```

常用分类文件名（URL 编码）：`心理.md`、`小说.md`、`文学.md`、`历史.md`、`经济.md`、`管理.md`、`计算机.md`、`科普.md`。条目形如 `- [书名 作者](https://url89.ctfile.com/f/<fid>?p=8866)（epub+mobi+azw3）`。注意：索引 ≠ 100% 覆盖，grep 无果先换分类再换关键词（书名去副词）。

**步骤 2 · 一键下载**（解析→双 API→直链→解压→清广告→验货，全自动）：

```bash
python3 $CT/scripts/ctfile_fetch.py "<诚通分享链>" "<输出目录>"
```

- 免登录、免 cookie、无验证码；免费通道限速约 30-50KB/s，一本 1-3 分钟；
- 直链有效期约 2 小时、限速，失败重跑即可（幂等，同名文件跳过）；
- zip 内常夹带广告文件（.url/.txt/图片），脚本自动清理，只留 epub/mobi/azw3；
- 解压后文件名是拼音（如 `YeXuNiGaiZhaoGeRenLiaoL.epub`），按库内规范整理为 `<书名> 全格式/<书名>.<ext>` 目录形态。

**步骤 3 · 链路红绿自检**（只读，不下载文件）：

```bash
python3 $CT/scripts/verify_ctfile_fetch.py          # 正跑须 9/9 GREEN
python3 $CT/scripts/verify_ctfile_fetch.py --neg     # 负控须 9/9 全转红
```

## 腿二：百度 AI 对话小程序（兜底）

**步骤 1 · 改书名参数**：把人类对话链接里的 `_chatQuery=` 值换成目标书名（URL 编码），token 会过期——过期后让甘在微信里重新打开小程序分享新链（人类操作入口）。

**步骤 2 · 渲染扒链＋下载**（一条命令跑完：无头浏览器渲染对话页 → 扒百度网盘链 → bdpan 转存下载 → PDF 自验）：

```bash
python3 $CT/scripts/smartapp_pdf_fetch.py "<对话URL>" --download --out-dir "<输出目录>"
```

- 依赖：playwright-core ＋ 系统 Chrome（已装）；`bdpan` CLI 已登录（账号 stephen_om）；
- 只扒链不下载（无副作用，先看有没有货）：去掉 `--download --out-dir`；
- 静态抓取（curl）对这个页面无效——纯 JS 空壳，必须渲染。

**步骤 3 · 链路红绿自检**：

```bash
python3 $CT/scripts/verify_smartapp_pdf_fetch.py
python3 $CT/scripts/verify_smartapp_pdf_fetch.py --neg
```

## 落地后验货（每条腿都必须做）

```bash
file "<落地文件>"                       # PDF: %PDF-1.x；epub: Zip archive；mobi/azw3: BOOKMOBI
head -c 8 "<file>" | xxd                # 看 magic 字节
ls -la "<file>"                         # 大小与 API 报告的 file_size_bytes 逐字节核对
```

- PDF 还查页数：`grep -c "/Type /Page" <file>` 或脚本自验输出；
- **负控制习惯**：拿一个明显不是书的文件（如 epub）跑 `file` 应报非 PDF——证明校验器能分辨，不是永远绿；
- 三格式书整理为 `<书名> 全格式/` 目录（参照库内《蛤蟆先生》《也许你该找个人聊聊》形态），PDF 直接平铺。

## 红线

1. **下载终点＝本地 `books/_source/`，不过夸克中转**——转存是闲鱼推广返利线的入场券，与蒸馏无关（书籍蒸馏铁律，甘 2026-10-17 定）；
2. 账号凭据（bdpan/夸克 cookie、小程序 token）**不进任何对外产物**；token 过期找甘重取，不猜不绕；
3. 报数必须带归因（哪条腿、哪个源、大小多少），禁印象式断言；
4. 两条腿都依赖外部服务：诚通仓库可能被 DMCA、百度 token 会过期——脚本和 SOP 是资产（已固化），源是消耗品（会死）；重新审视触发条件＝仓库被删/链大面失效/百度 token 长期过期，届时换优先级即可，结构不动；
5. 本 skill 是路由层：**改脚本/SOP 去 368 容器改**（`$CT/scripts/`＋`$CT/SOP/`），不在 skill 目录复制代码。

## Resources

- `references/source-legs.md` — 两腿详细对比、上游索引结构、选用裁决全文、失败分支与已踩坑（Bash grep 不认 `\|`、macOS unzip 无 `-O`、Chrome 不走 env 代理等）。详细 SOP 真源：`$CT/SOP/诚通网盘书源扒取runbook.md`、`$CT/SOP/智能小程序书源扒取runbook.md`。
