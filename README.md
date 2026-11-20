# Agent Skills 作品集

自写的 AI Agent skill 合集。每个 skill 是一个独立目录，含 `SKILL.md` 与配套脚本。

共 37 个 skill。

## devtools

- **[hermes-approvals-switch](./hermes-approvals-switch/)** `v1.0.0` — 安全、幂等地在三个档位间切换 Hermes Agent 的 approvals.mode，日常 smart（风险动作前拦你确认）、全确认 manual（每步都问）、全托管 off（裸奔，不推荐）。每次切换带配置备份与正确重启路径，杜绝改坏、重启卡死、四处撞壁。触发短指令：切审批档 / 审批开关 / Hermes档 / …
- **[lighthouse-agent-hardening](./lighthouse-agent-hardening/)** `v1.0.0` — 在腾讯云轻量应用服务器上为常驻、有真实能力（命令/文件/外联/凭证）的自主 Agent 做安全加固的操作指南。channel-agnostic，加固锁的是 Agent 自身能力边界，与经哪个聊天频道指挥它无关。覆盖跨地域定位实例、升级修 CVE、收紧 SSH、到期续费提醒、写 SOUL 安全指令、出网白名单权衡。面向非…

- **[chrome-cdp-tab-scraper](./chrome-cdp-tab-scraper/)** `v-` — 通过 Chrome DevTools Protocol 接入用户已打开的浏览器标签，读取已登录页面的实时 DOM 内容；不另起浏览器、不新建 profile。
- **[cn-pip-install](./cn-pip-install/)** `v-` — 中国网络下 pip 装包前的标准动作：先探生效源，源为空或指向海外时主动提醒改国内镜像，不静默走慢速海外源。
- **[container-call-audit](./container-call-audit/)** `v-` — 审计多个 WorkBuddy 容器在指定时间窗内对某项能力的真实调用量；先探记录结构再检索，区分「真调用」与「只是提及」。
- **[gh-git-windows-setup](./gh-git-windows-setup/)** `v-` — 在受限 Windows 机器上打通 GitHub 读写：凭证持久化 + 可用的 HTTPS/SSH git 传输，两条链路分别验证后给出可复现的安装步骤。
- **[html-render-png](./html-render-png/)** `v-` — 把本地 HTML 精确渲染成 PNG（卡片图 / 海报 / 固定比例图），解决生成式图片无法保证中文文字与版式准确的问题。
- **[ima-kb-online-bulk-read](./ima-kb-online-bulk-read/)** `v-` — 在线批量读取知识库里的几十上百个文档而不整包下载：串行 + 退避 + 断点，只落文本缓存。
- **[market-skill-patch](./market-skill-patch/)** `v-` — 维护从市场安装的 skill 的补丁：产出可重打的补丁副本与重打判据，避免升级整包覆盖后修改丢失。
- **[tencent-edu-course-scrape](./tencent-edu-course-scrape/)** `v1.0.0` — 把图文课程页整本抓成离线 Markdown 备考册，按模块/小节切分并本地化配图；先验证匿名可读再决定是否需要登录。
- **[wb-skill-publish-check](./wb-skill-publish-check/)** `v1.0.0` — 打包 skill 上架市场前的自检器，一次性验完目录层级、frontmatter 展示字段、头像体积三道平台硬约束。
- **[windows-playwright-install](./windows-playwright-install/)** `v-` — 在 CDN 不可达 / 缺 VC++ 运行时的 Windows 机器上安装 Playwright + Chromium 的可重复流程，覆盖两种典型失败。

## 通用

- **[injection-layer-governance](./injection-layer-governance/)** `v1.2.0` — AI Agent「注入层」治理 —— 把每轮对话开局被自动注入的记忆 / 规则 / 身份 / 目录等对象， 从「越线即故障」管成「越线之前先叫」。当需要做「记忆体检 / 记忆瘦身 / 记忆治理 /
- **[invariant-checklist](./invariant-checklist/)** `v0.3.0` — 用户说「我要一个 X」「建个 X」时用（X＝任意名词，库/表/词表/看板/流程/台账都行）。 先推导这个名字天然该守住的工程底线（不重/不漏/不丢/可溯/可解释/受控/新鲜），
- **[premise-audit](./premise-audit/)** `v0.1.0` — 落施工方案 / 写排期 / 定判据之前，把方案里那些「因为…所以…」的**前提**逐条变成 **能红能绿的断言**，真跑一遍。验不过 ⇒ 改判据或改方案，⛔ 不许带病开工。
- **[memory-clearance](./memory-clearance/)** `v1.3.0` — 收尾清算 —— session 收尾时「过程信息即时删除」的执行清单。 当用户说「收尾」「收尾清算」「清算」「过程信息删除」，或本 session 出现待办被关闭 / 完成 /
- **[html-long-doc-to-markdown](./html-long-doc-to-markdown/)** `v-` — 把「长 HTML 文档 / 网页版手册 / 平台导出的 HTML」保真转成 Markdown，并做结构对账。 当需要「html 转 md / 网页转 markdown / 出一份 md 版 / 把 HTML 手册变文本 / 长文 HTML 转 markdown」，
- **[md2poster-pipeline](./md2poster-pipeline/)** `v0.1.0` — 368 容器贴图号编辑器的「约定符号 md → 贴图号 PNG」替补流水线。 当 `web/mapper.py`（零触碰，只实现 `## ` 分页与 `|表格|`）无法识别 §六 约定符号
- **[md-to-docx](./md-to-docx/)** `v-` — Markdown → Word（「转 docx」）的固化路径。当甘晓东说「转docx / 转成 docx / md 转 Word / 出个正式件 / 出 docx」， 或任何本地 .md 需要变成本地可编辑 .docx 时使用。默认走「轻量路」= 本地编辑器通道（create_doc → doc_insert_mark…
- **[mac-universal-bundle-verify](./mac-universal-bundle-verify/)** `v-` — macOS universal(.app) 或任何 fat Mach-O 包在发布/交付给他人前的核验清单——覆盖「cargo tauri build 不签名」这个必踩坑、切片级架构核验（不靠 lipo 自报）、依赖库/符号/ABI 差异判读、以及如何用源码层扫描把「跨架构风险」从『不知道』量化成『只差运行时确认』。当…
- **[svg-long-image](./svg-long-image/)** `v-` — 用「SVG 代码 → Chrome headless → PNG」出长图（贴图号/小绿书、知识图解、信息长图、海报、公众号配图）。当甘晓东说「出图 / 出长图 / 做一张贴图号 / 知识图解 / 把这篇做成图 / 生成图片文件」，或需要把结构化知识做成可发布的 PNG（任意画幅，含 1242×1656 的 3:4 竖版…
- **[render-parity-check](./render-parity-check/)** `v-` — 同一份内容要在多个渲染宿主里保持一致时（编辑器「编辑面 / 预览 / 导出」三态、Shadow DOM vs 真页面、前端实时渲染 vs 服务端重建 HTML）的**体检法**：用同一份内容 × N 个宿主，比 `getComputedStyle` 真值，先拿到「能红能绿」的前置诊断，再动代码。当用户说「预览跟导出不一…
- **[web-ui-click-harness](./web-ui-click-harness/)** `v-` — 用 Chrome headless + 离线 harness「派发真实 click」端到端验证网页交互（点选/弹框/状态回显），并带红绿负控制。当出现「脚本全绿但真机点了没反应」「交互类 bug 抓不到」「前端验收靠肉眼」时用。触发词：真实点击验证、click 回路、harness、前端交互验收、能红能绿。
- **[fact-check](./fact-check/)** `v-` — 004 口播 / 005 公众号写作共用的强制事实校验闸门，根治事实错误（727「开车上船」头号根因）。 当 004/005 写作时，必须 read 本 SKILL.md 并执行 E-a~E-e 全流程：检索 claim → 建 references
- **[koubo-diff-resolver](./koubo-diff-resolver/)** `v-` — 文本修改自动识别器。当用户贴回一段修改后的文本（从 Word/WPS 改好贴回），且当前对话已有原始草稿时， 自动对比原文与修改版，输出结构化变更（删除/新增/修改），无需用户说明改了哪里。
- **[wb-dock](./wb-dock/)** `v-` — 把待办/规则/提示词写进 WB Dock 面板（真相源 ~/wb-dock/dock.json，Windows 是 %USERPROFILE%\wb-dock\dock.json）。当用户说「挂到 dock」「写进 dock」「把这条待办放面板上」「记到面板上」「把这条规则加到 dock」「从别的容器/别的机器往面板里…
- **[xmind-to-report-video](./xmind-to-report-video/)** `v-` — 将 xmind 思维导图转换为会议投屏 16:9 汇报视频。Remotion 4 + 本机 Chrome Headless，12 个标准场景分镜，Constants-First 文案。
- **[ebook-fetch](./ebook-fetch/)** `v-` — 找电子书并落地本地文件的正式能力（两条书源腿：诚通网盘优先、百度 AI 对话小程序兜底）。当需要找书、下载电子书（epub/mobi/azw3/pdf）、测试某个推文/仓库推荐的电子书源能不能用、或给书籍蒸馏流水线补原料时使用本 skill。覆盖：按书名搜诚通索引、一键下载三格式、百度小程序渲染扒 PDF 链、下载后验…
- **[ima-zip-migrate](./ima-zip-migrate/)** `v-` — 从 IMA 知识库下载 zip 迁移包并安全解压落位到本地工作区（跨机迁移场景）。当需要「从 IMA 共享库取 zip → 下载 → 解压到目标目录 → 校验结构 → 回填进度回执」时使用。触发词：迁移包、zip 落地、从 IMA 下载压缩包、跨机迁移解压、记忆资产包。
- **[skill-trim-audit](./skill-trim-audit/)** `v-` — 副业雷达 · skill 使用度审计与交叉瘦身（A∪B 判据）。当甘晓东说「skill 瘦身 / 能力盘点 / 交叉比对 / 哪些 skill 没用了 / 清理 skill」、或**找替代 API / 某接口太贵 / 付费接口有无更便宜的覆盖**
- **[wb-library-access](./wb-library-access/)** `v1.0.0` — WB 资料库（workbuddy 内置资料库）读写 canonical 路径与鉴权流程。 凡涉及 资料库 / 空间文档 / 老甘素材库 的读、写、搜、列操作，或 space_api.py 报错时使用。
- **[wb-transcript-mining](./wb-transcript-mining/)** `v-` — 从 WorkBuddy 本地会话 transcript（jsonl）里挖「历史对话原文 + 下文」。 当需要**某段历史对话的逐字原文或它之后 AI 怎么回的/后续结论**，而 `conversation_search`
- **[wb-client-probe](./wb-client-probe/)** `v-` — WorkBuddy 客户端「机制级取证」——直接搜 app.asar 源码，实证平台到底注入/读取了哪些文件、 各注入块字符上限是多少、某段提示语出自哪里、某个记忆/技能开关叫什么。当需要回答「X 文件会不会
- **[workspace-archive-closure](./workspace-archive-closure/)** `v-` — 跨 workspace 物理收口归档工作流。当需要把已迁移/已退役的 WorkBuddy 容器（沙盒、空壳、旧项目空间）移出工作区归档、清理 workspace 列表、做机器侧物理收口时使用。触发词：物理收口、容器归档、归档工作区、清理 workspace、移出工作区、收口执行。核心：先只读扫描防漂移、再确认范围与落点…
- **[buying-reason-rewrite](./buying-reason-rewrite/)** `v-` — 把功能、能力、原理类卖点文案改写成「买的理由」：用户视角的一句话结果，带比较级，读者不用推理。
- **[session-continuity](./session-continuity/)** `v1.0.0` — 用「收尾 + 继续」把长任务切成多个干净 session，避免上下文腐烂与跨会话失忆，进度与状态可接力。

## 分析方法

- **[ai-signal-calibration](./ai-signal-calibration/)** `v-` — 给中文文本加「AI 味」判据之前，先用自己的真实稿校准业界三信号（句长分布方差 / 连接词密度 / 段落节奏），避免照搬结论把方向判反。

---

每个 skill 按 Claude/WorkBuddy skill 规范编写，可直接复制到对应 skills 目录使用。
