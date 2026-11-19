---
name: xmind-to-report-video
description: 将 xmind 思维导图转换为会议投屏 16:9 汇报视频。Remotion 4 + 本机 Chrome Headless，12 个标准场景分镜，Constants-First 文案。
license: MIT
allowed-tools: Bash(node:*), Bash(npm:*), Bash(curl), Bash(unzip), Bash(ls), Read, Write, Edit, Glob, Grep, Skill
metadata:
  source: <客户方>·AI 应用与渗透汇报视频 2026-08-09
  generator: CCS (WorkBuddy)
---

# XMind → 汇报视频（Remotion）

把结构化思维导图一键生成会议投屏 16:9 汇报视频。

## 适用场景

- 战略汇报、董事会汇报、年度/季度复盘
- 业务线渗透进度展示
- 多机多账号的运维/算力拓扑可视化
- 价值链 AI 化拼图讲解

## 不适用场景

- 复杂真人/口播拍摄类（用剪映/达芬奇）
- 需要逐字口型同步的精细动效（Remotion 擅长程序化生成，不擅长真人合成）
- 横屏电视广告（建议剪映/PR）

## 一句话流程

解压 xmind → 抽取节点结构 → 按节点类型映射到 12 个标准分镜 → 改文案 → 渲染 MP4。

## 标准分镜模板（12 个场景 / 100 秒）

每个场景的 CONTENT 常量在文件顶部独立成块，改文案只需动这一块。

| # | 场景 | 用途 | 节点来源映射 |
|---|------|------|--------------|
| 01 | 开场 | 标题 + 公司名 + 副标题 + 日期 | 任意 |
| 02 | 全景总览 | 三大并列板块 | 根节点 → 顶层 3 个分支 |
| 03 | 中枢拓扑 | 一个中心 + 若干辐射节点 | 中心节点 + 直接子节点 |
| 04-05 | 业务线汇聚 | 两路采集 + 沉淀 | 两路分支 + 沉淀节点 |
| 06 | 分布式作业 | N 个并列执行单元 | 多个相同层级子节点 |
| 07 | 多源数据回流 | 多个来源 → 一个汇总 | 多源 + 一汇聚 |
| 08 | 统一入口 | 一个中心向 N 路分发 | 中枢 + 输出分支 |
| 09 | 双区暂驻 | 两个并列的「维持态」 | 两个并列占位节点 |
| 10 | 基建能力矩阵 | 两列能力卡 + 状态标签 | skill 类 + 脚本类分组 |
| 11 | 渗透总览 | 表格 + 进度条 + 阶段标签 | 每条业务线一阶段 |
| 12 | 收尾 | 数字 + 3 条结论 + 版权 | 任意 |

## 字体策略

优先用系统字体栈，不下载远程字体：

```ts
export const FONT = '-apple-system, "SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
```

## 本机 Chrome 绕过 Chrome Headless Shell 下载

`remotion still` / `remotion render` 默认会下载 `chrome-headless-shell-mac-x64.zip`（约 145MB）。
在某些网络环境（限速/慢速）会卡 30 分钟以上。

绕过办法：直接用本机 Chrome：

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
npx remotion still src/index.ts <comp-name> out.png \
  --frame=100 --browser-executable="$CHROME"
```

也支持 Edge / Chromium / Brave：

```bash
EDGE="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
--browser-executable="$EDGE"
```

## ffmpeg 兼容坑与 evermeet 静态版（本机必做前置）

`Remotion render` 把图片帧合成 MP4 必走 ffmpeg。**本机（macOS 12.7.6 / Intel x86_64）Remotion 自带的 ffmpeg 二进制报缺符号 `AVCaptureDeviceTypeContinuityCamera`（macOS 13+ API），直接跑不了**。`brew install ffmpeg` 在本机网络环境也会卡死。

解法：用 evermeet.cx 静态编译的 ffmpeg 8.0（免依赖），已沉淀在：

```
~/.workbuddy/binaries/ffmpeg-darwin-x64/   # ffmpeg + ffprobe + README.txt
```

替换步骤（每次 `npm install` 重装后都要重做）：

```bash
DEST=node_modules/@remotion/compositor-darwin-x64
cp "$DEST/ffmpeg" "$DEST/ffmpeg.bak"            # 备份原版
cp ~/.workbuddy/binaries/ffmpeg-darwin-x64/ffmpeg "$DEST/ffmpeg"
cp ~/.workbuddy/binaries/ffmpeg-darwin-x64/ffprobe "$DEST/ffprobe"
chmod +x "$DEST/ffmpeg" "$DEST/ffprobe"
```

> ⚠️ evermeet 版**不含 libfdk_aac**，但含 libmp3lame。Remotion 默认音频编码 aac 会失败 → 渲染命令必须加 `--audio-codec=mp3`。

## 渲染参数（Intel Mac / 4 核 8G 实测）

```bash
export NODE_OPTIONS="--max-old-space-size=6144"
npx remotion render src/index.ts <comp-name> output.mp4 \
  --browser-executable="$CHROME" \
  --concurrency=1 \
  --audio-codec=mp3 \
  --jpeg-quality=82 \
  --pixel-format=yuv420p \
  --codec=h264 \
  --log=info
```
> `--concurrency=1` 必填：本机 4 核 8G 上 concurrency=2 会让 Chrome 超时崩溃。
> `--audio-codec=mp3` 必填：evermeet 版 ffmpeg 无 libfdk_aac，Remotion 默认 aac 会失败；mp3 走 libmp3lame 可用。

预期渲染速度：实测 3000 帧（100秒@30fps）单并发约 17m50s（≈2.8 fps）。

## 项目结构

```
remotion-videos/
├── package.json
├── tsconfig.json
├── remotion.config.ts
├── public/assets/             # BGM / 字体 / 图片
│   ├── bgm.mp3
│   └── ATTRIBUTION.txt
├── src/
│   ├── theme.ts              # 品牌色 / 时长表
│   ├── ui.tsx                # 通用组件 + 动画工具
│   ├── VideoComposition.tsx  # 主组合 + BGM 音量曲线
│   ├── Root.tsx              # Composition 注册
│   ├── index.ts              # registerRoot
│   └── scenes/
│       ├── Scene01Opening.tsx
│       ├── Scene02Overview.tsx
│       └── ...
└── output/
    ├── <name>.mp4
    └── stills/                # 抽样静帧（QA 用）
```

## Constants-First 设计

每个 Scene 文件结构：

```ts
// ============ 可编辑文案 ============
const CONTENT = {
  index: "章 节 X",
  title: "...",
  sub: "...",
  items: [...],
};
// ===================================

export const SceneX: React.FC = () => { ... };
```

改文案只需动 CONTENT 块。

## 复用流程

1. 复制 `remotion-videos/` 整个目录（保留 src / public / output / 配置文件即可，node_modules 可删、用时重装）
2. 替换 `public/assets/bgm.mp3`（或删掉 Audio 组件）
3. 改 `src/theme.ts` 的品牌色（如有）
4. 逐个改 `scenes/*` 顶部的 CONTENT
5. 改 `VideoComposition.tsx` 里的 `SCENES` 数组
6. `npm install` 重装依赖
7. **复制 evermeet ffmpeg 到 compositor 目录**（见上文「ffmpeg 兼容坑」节，必须做）
8. 用本机 Chrome + `--concurrency=1 --audio-codec=mp3` 渲染

## 性能红线

| 项 | 阈值 | 超限后果 |
|----|------|----------|
| backdropFilter: blur | 全片 < 10 处 | 渲染极慢 |
| 同屏粒子 / 流光 | < 40 个 | GPU 撑不住 |
| 同屏 SVG path 数 | < 20 条 | 渲染慢 |
| 全片总帧数 | < 4500 | 单次 25 分钟内 |

## 已知坑

1. macOS 版本低于 15 时，Chrome 150+ 仍可工作但会报 macOS older than Sequoia 警告，可忽略。
2. ccMixter API 的 Node HTTP 客户端有 Bug（错误 Expected HTTP/），用 curl 直接请求能正常工作。下载 BGM 时务必带 `Referer: https://ccmixter.org/files/<user>/<id>`。
3. CC BY 3.0 商用授权的 BGM 在 ccMixter 必须查 `lic=open` 才能命中，默认搜索结果常常是 NC（非商用），别拿来直接用。
4. `Audio` 组件在 4.x 仍可用，未完全迁到 `@remotion/media`，放心用。

## 扩展指引

- 加新场景：复制现有场景 → 改 CONTENT → 加入 `theme.ts` 的 `SCENE_FRAMES` 数组 → 加入 `VideoComposition.tsx` 的 `SCENES` 数组
- 加 Logo：水印放右下，参考 `Footer` 组件
- 加双语：CONTENT 加 `en/zh` 字段，渲染时按语言切换
- 加字幕：把字幕 timing 数组 + Audio 同步