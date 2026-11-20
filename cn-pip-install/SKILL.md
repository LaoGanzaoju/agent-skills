---
name: cn-pip-install
description: 中国工作机（<本机>/Windows）给 Python 装包前的标准动作：先探 pip 生效源，源为空或指向海外 pypi.org 时主动提醒用户配代理或改用国内镜像（本机首选阿里；清华在本机 pip 侧已实测失效），不静默走海外源。触发：pip install / 装依赖 / 建 venv / 部署运行环境 / 初始化环境。
agent_created: true
---

# 中国工作机 pip 安装源探测

## 用途
中国网络下 pip 默认源 pypi.org 在海外，GB 级包下载速率可低至数十 KB/s（本机实测 34KB/s），安装耗时数小时。本 skill 把"安装前先探源、海外即切镜像"做成标准动作，杜绝闷头走海外源。

## 何时触发
用户要求 `pip install` 任意包、安装 Python 依赖、建 venv、部署或初始化运行环境；任何会落到 `python -m pip install` 的前置步骤。

## 步骤

### 1. 探源
运行 `python -m pip config list -v`，并读取 `PIP_INDEX_URL` 环境变量。

完成判据：已取得 global/user/site 三处 index-url 值与 PIP_INDEX_URL 值，能判定当前生效源。

- 三处均无 index-url 且 PIP_INDEX_URL 为空 → 默认官方源 `https://pypi.org/simple`（海外）。
- index-url 含 `pypi.org` / `files.pythonhosted.org` / `pypi.python.org` → 海外源。
- 含 `tuna.tsinghua.edu.cn` / `mirrors.aliyun.com` / `pypi.douban.com` / `mirrors.cloud.tencent.com` → 国内镜像，跳到步骤 3。

### 2. 海外源即提醒，不静默开装
安装大包（torch / tensorflow / 大模型 / 依赖树深）前，先向用户报告并给选项，未经确认不得开装：

- 报告：「当前 pip 走海外官方源，中国网络下可能极慢（本机实测 34KB/s，GB 级包需数小时）」。
- 选项：
  - A) 国内镜像重跑（**本机首选阿里**）：`python -m pip install -i https://mirrors.aliyun.com/pypi/simple <包>`。**不要首选清华**——本机 pip 侧已实测失效（见下「镜像可用性」）。
  - B) 配置代理（用户侧网络）。
  - C) 继续硬等（须用户明确确认）。

完成判据：用户已选 A/B/C 之一，或源已是国内镜像。

### 3. 安装执行纪律
- 用 `python -m pip`（不用裸 `pip.exe`——后者触发 pip 自我保护致 `&&` 链短路失败）。
- managed Python 用专用 venv 隔离，不污染共享环境。
- Git Bash 精简版无 `sleep`：等旧进程退出用 TaskStop 或分两条消息，不在命令里用 `sleep` 串行等待（整条 `command not found` 失败）。
- 长安装用 `run_in_background: true`，完成由系统通知，不空轮询。

完成判据：包导入验证通过（`python -c "import torch"` 等），或用户确认装完。

## 镜像可用性（2026-09-22 复测 · 选源以此为准）
- **阿里源 `https://mirrors.aliyun.com/pypi/simple`：可用**。实测 pyyaml / tiktoken / jsonschema 全部秒级装完（tiktoken 940KB wheel 正常下载）。
- **清华源 `https://pypi.tuna.tsinghua.edu.cn/simple`：本机 pip 侧失效**。表现：pip 只打印 `Looking in indexes: ...` 后直接 `ERROR: Could not find a version that satisfies the requirement <pkg> (from versions: none)`，**不报连接错误却取不到任何版本**；同一时刻用 `urllib` 直取该源 `/simple/<pkg>/` 返回 **200 / 178KB**，说明网络通、是 pip 请求层（PEP 691 JSON 索引）被中间环节拦下。**遇此报错直接换阿里源，不要反复重试清华**。
- 本机存在环境代理：`HTTP_PROXY` / `HTTPS_PROXY` = `http://localhost:2451`（经代理访问 pypi.org / 阿里 / 清华均返回 200）。
- 海外源历史实测：torch 124MB + 深依赖树，34KB/s，1h24m 未装完；切镜像后分钟级完成。
- 装完必查：`python -m pip list` 或导入验证。`pip config list -v` 三处（global `C:\ProgramData\pip\pip.ini` / user `<HOME>\pip\pip.ini` 与 `AppData\Roaming\pip\pip.ini` / site `<venv>\pip.ini`）本机均无 index-url，`PIP_INDEX_URL` 也为空 —— 实际选源由命令行 `-i` 与环境代理决定。

## 实测对照（海外源历史证据）
- 海外源 pypi.org：torch 124MB 起步 + 深依赖树，实测 34KB/s，1h24m 未装完。
- 切镜像源：torch 124MB 18 秒下完（6.7MB/s），整体约 200 倍提速，分钟级装完。

## 可选：固化全局镜像
用户希望所有 venv 默认走国内镜像时，写用户级 `<HOME>\pip\pip.ini`：
```
[global]
index-url = https://mirrors.aliyun.com/pypi/simple
```
改全局配置前须先向用户确认。
