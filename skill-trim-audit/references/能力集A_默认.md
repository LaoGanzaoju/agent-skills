# 能力集 A · 副业链路保留名单（脚本保护清单）

> 一行一个 skill 名；`##` 建分组；`#` 起注释。
> 判定逻辑：**在此名单内 或 近 N 天有真实调用 → 保留；两者皆非 → 候选瘦身。**
> 维护：新增 skill 若属副业链路，回补到此文件；甘晓东点名保留的，追加到「用户点名保留」组。
> 口径来源：`雷达容器总定义_..._2026-09-09.md`（§3/§4）· `副业雷达_穷尽收敛SOP.md`（§三/§五）· `副业落地项目清单_..._2026-09-07.md`（P1–P7）· `周一副业雷达_任务规格` · 用户级自定义指令「技能档位」。

## 主链路·监控信源
gzh-subscribe
wechat-search
wechat-fastest-growing
wechat-similar-account
wechat-account-analyzer
wechat-channels-crawler
trending-hub
xiaohongshu-search
xiaohongshu-lowtop
xiaohongshu-similar-account

## 主链路·搜索
multi-search-engine
doubao-websearch
tencent-yuanbao-standard-search

## 主链路·扒取
radar-intake
video-downloader
twitter-video-downloader
youtube-digest
xiaohongshu-crawler
lingyi-wx-video-decomposer-exp
web-access

## 主链路·转写
pdf-image-text-extractor
openai-whisper
tencentcloud-ocr
tencentcloud-ocr-extractdocagent          # 待裁决，但同族依赖：删则连带废掉已验证 OCR 路径
tencentcloud-ocr-recognizetableaccurate   # 同上

## 主链路·复写扩写
wechat-article-pro
xiaohongshu-write
x-longform-post

## 主链路·合规
multi-wordcheck
fact-check

## 主链路·分发（P8 多账号已交蚁小二）
wechat-publisher
lovstudio-wechat-article-operator

## 双出口·P1/P6 输出
md-to-pdf-cjk
md-to-docx
minimax-docx
minimax-xlsx
pptx-generator
markitdown-skill
xmind-skill
xmind-to-report-video

## 双出口·P2 造 skill
nuwa-skill
lovstudio-skill-distiller
skill-scanner
skill-vetter

## 双出口·P6 FDE
fde-cannon
fde-l0-scaffold

## 双出口·P4 小工具
frontend-dev
impeccable

## 基础设施
ima-skill
ima-zip-migrate
skillhub-daily
github

## 主链路·付费接口能力（2026-09-27 甘令登记 ⇒ 每次盘点顺带做替代侦察）
# 这几条**不是 skill 名**，是「靠付费接口实现的能力」。登记进 A 集的目的是：
# 每次维护名单时它们都在视野里，可被问一句「现在有更便宜的覆盖方式吗」（见 SKILL.md §八）。
# 单价为 2026-09-27 审计实测（真账以厂商账单为准；调价时回来改这里的注释）。
视频号·账号维度取链                  # Just One（get-account-videos ¥0.50/次 + get-video-download-url ¥0.30/条）——
                                     # **当前唯一**能「按账号身份枚举全部作品→取直链」的通道 ⛔ 无付费即无此能力。
                                     # 红狐便宜(¥0.036–0.054)但只有单条解析、没有账号枚举 ⇒ 是分工不是替代。
视频号·单条分享链接解析              # 红狐 parseWork/parse ¥0.054/次，腾讯 CDN 免鉴权直链，费率可接受，暂不找替代。
公众号·历史文章枚举                  # Just One get-account-history-articles/v2 ¥0.40/次（当前低价，同族一起看）
ASR·火山云转写                       # 按秒计费；本机 faster-whisper 因 8G OOM 禁用 ⇒ 现役唯一方案，暂不找替代。

## 技能档位（自定义指令·三层强度）
writing-for-agents
grilling
diagnosing-bugs
tdd
handoff

## 办公文档链（走插件通道，不归 ~/.workbuddy/skills 管理，故不入本保护名单）
# tencent-docs-routing / tencent-docx / tencent-local-office-edit —— 插件 skill，
# 由 md-to-docx（本机 skill）调用，脚本会自动归入「外部能力」组，无需在此登记。

## 他空间在用 / 跨容器复用
mac-align
workspace-archive-closure
koubo-diff-resolver
lark-unified
skill-trim-audit

## 用户点名保留（2026-09-12 / 2026-09-22）
cangjie-skill
cli-anything-hub
github-pages-auto-deploy
laogan-perspective                                # 女娲蒸馏老甘人设（A2试点）2026-09-22 点名保留，防瘦身误删（人物skill·近30天零调用）

## 用户曾指定必留（2026-08-12 标注，2026-09-12 仍未推翻）
workbuddy-asset-migration
