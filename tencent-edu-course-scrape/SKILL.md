---
name: tencent-edu-course-scrape
title: 腾讯云教育课程页全量抓取
description: 把 cloud.tencent.com/edu/learning 的图文课程（如 FDE 官方课程）整本抓成离线 markdown 备考册：正文全文 + 配图本地化。含 agent-browser 安装坑与免登录判定。
version: 1.0.0
author: CCS
trigger: 用户要求"扒 / 全量抓 / 下载"腾讯云 edu 课程页内容时
agent_created: true
display_name: 腾讯云教育课程页全量抓取
display_name_en: Tencent EDU Course Full Scrape
description_zh: 抓取腾讯云教育课程页（cloud.tencent.com/edu/learning）全文与配图，组装为离线可看的 markdown 备考册。
description_en: Fully scrape Tencent Cloud EDU course pages (text + images) into an offline markdown study book.
---

# 腾讯云教育课程页全量抓取

## 适用场景
`https://cloud.tencent.com/edu/learning/course-XXXX-...` 类图文课程页（实测对象：FDE 官方课程 course-4742-84529-84539）。输出：单份 md（全文按模块/小节切分）+ 本地化配图。

## 核心结论（实测 2026-09-27）
1. **正文不需要登录**。WebFetch/匿名 curl 拿到的壳页 404/空 ≠ 需登录；COS 私有桶（cert-private-*）直链 403 也 ≠ 需登录。**真实浏览器里页面匿名即渲染全文**。先开浏览器验证，再决定要不要麻烦用户登录。
2. 页面按**模块整体渲染**：点击任一小节后，`document.querySelector('main').innerText` = 该模块全部小节文本。N 个模块 = N 次点击即全量，不必逐节抓。
3. 图片在**公开桶**（academy-pub-*.cos.ap-guangzhou.myqcloud.com），带 Referer 可直下；URL 路径含 `images/<lesson>/<file>`，天然按小节归组。

## 工具准备（Windows 实测坑）
```bash
# 坑1：npm 官方源国内卡死（6分钟零输出）→ 直接上镜像
npm install -g agent-browser --registry=https://registry.npmmirror.com   # 6秒装完

# 坑2：agent-browser install 下载 Chromium 走 storage.googleapis.com 会超时
#      → 不下载，直接用本机 Chrome：
agent-browser --executable-path "C:\Program Files\Google\Chrome\Application\chrome.exe" open "<课程URL>" --headed
```
首次 `open` 可能长时间不返回（CLI 卡住但浏览器已起），另开 shell 直接 `snapshot` 即可，daemon 共享会话。

## 抓取流程
1. `agent-browser snapshot` 确认正文可见（看 `main` 下有无课程文本）。
2. 侧边栏 DOM：模块=`span.toc-l1-text`，小节=`span.toc-l2-text`。用 JS 文本前缀匹配点击（ref 会漂移，别用 snapshot ref）：
   ```js
   (()=>{const s=[...document.querySelectorAll('span.toc-l2-text')].find(e=>e.textContent.trim().startsWith('1.1 '));s.parentElement.click();return s.textContent.trim();})()
   ```
   点击后 `sleep 2` 再取内容。
3. 每模块：`agent-browser eval "document.querySelector('main').innerText"`（输出是 JSON 字符串，二次 json.loads 解码）+ `eval "JSON.stringify([...document.querySelectorAll('main img')].map(i=>({src:i.src,alt:i.alt})))"`。
4. 图片批量下载（带 `Referer: https://cloud.tencent.com/`），按 `images/<lesson>/` 落本地 `assets/images/`。
5. 组装 md：按 `CHAPTER 0X · LESSON N.N` 标记切分。**注意 2.2 上/中/下 这类标记带后缀**（`LESSON 2.2 · 上`），正则须含 `(?:\s*·\s*[上中下])?`，图片目录名无空格（`2.2上`），映射时拼接。
6. 复核三件套：小节标题数、图片引用数、未引用目录数，全对齐才交付。
7. `agent-browser close` 收尾（必跑）。

## 已知边界
- 视频课节（若有）只拿到播放器，不抓视频本体。
- innerText 会丢失图内文字与精确插图位置；配图按小节归组挂在节尾。
- 登录墙真实存在时（正文也 403/空壳），才需要用户登录后走同一流程。
