---
name: ima-kb-online-bulk-read
description: 在线批量读取 IMA 知识库多个文件（禁止整包下载场景）。当用户要求「在线读 IMA 库 / 通读知识库 N 个文件 / 别批量下载、在线读」时使用。封装 IMA OpenAPI 三头协议 + 签名头 + 限流退避 + 断点续跑，只落文本缓存不下素材包。触发词：IMA 批量读、在线读知识库、通读 IMA、ima-kb 在线读。
agent_created: true
---

# IMA 知识库在线批量读

## 适用场景
- 用户要求通读 IMA 知识库某个文件夹（几十上百个 md），但**明令禁止整包下载**（"78个文件你都拉下来再读明显不合理，在线读"）。
- 已安装 `ima-skill`，但批量顺序读 77+ 文件时直接用 API 更可控（可节流/退避/断点）。

## 硬纪律
- **只落文本缓存**，不下载素材包/附件（zip 迁移走 `ima-zip-migrate`，不在此范围）。
- 凭据不外泄、不写死进脚本（读 env 或 conf 文件）。
- 限流时**串行 + 退避**，禁止并发轰接口。

## 凭据（三头协议）
```python
headers = {
    "ima-openapi-clientid": <client_id>,
    "ima-openapi-apikey":  <api_key>,
    "ima-openapi-ctx": "skill_version=read-only-tool",  # 自写工具可自定义
    "Content-Type": "application/json",
}
```
- env 变量名：`IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY`
- 或读 conf 文件：`~/.workbuddy\skills\ima-skill\` 下 `client_id` / `api_key` 两个文件
- ⚠ **坑**：skill 内部代码调用参数名是 `clientid`/`apikey`（无下划线），与 conf 文件名 `client_id`/`api_key`（有下划线）**不一致**，别串。

## API 链路
1. `POST openapi/wiki/v1/<ops>` 以 `https://ima.qq.com` 为 base（具体路径以 ima-skill 的 `ima_api.cjs` 为准，勿凭记忆）
2. `get_knowledge_list`：cursor 分页列文件；**文件夹的 `media_type=99`**
3. `get_media_info`：取 `url_info.url` + `url_info.headers`
4. 抓正文：`GET url` **必须带上 `url_info.headers`**（含签名头）

## 两个 403 坑（实测）
| 现象 | 根因 | 解法 |
|---|---|---|
| 抓正文 403 | 缺签名头 `X-IMA-Sign` / `X-IMA-Create-URL-Time` / `X-IMA-Platform` | `fetch_text(url, extra_headers=ui.get("headers"))` 原样带上 |
| `get_media_info` 403 | 并发触发 API 限流 | 改**串行**：每次调用前 `sleep(0.6~1.2s)` + 指数退避重试（`2**i + random()`，4 次）+ 按已缓存文件**断点续跑** |

判断限流 vs 凭据问题的独立验证：停 25s 单发一次成功 → 凭据/权限没问题，是限流。

## 落地形态
- 文本缓存目录 `cache/*.md`（UTF-8，多编码兜底 `utf-8→gbk→gb18030→latin-1`）
- `manifest.json`：每文件 字数/行数/标题/head，供索引用
- 结果计数：`OK N / FAIL M / TOTAL xx字`，全部成功才算完成

## 参考实现
- `<PROJECT_ROOT>`（最小 API 客户端：list/walk/media_info/fetch_text）
- `<PROJECT_ROOT>`（串行抓取 + 退避 + 断点 + manifest）
- 首次跑通记录：2026-08-31 77/77 成功 / 229,318 字（详见该项目 `.workbuddy/memory/2026-08-31.md`「在线读方案」段）

## 交付建议
读完 77 篇后建议按「目的」出选读路由索引（见参考 `IMA信封计划_L0-L2_文件索引_2026-08-31.md` 的 §二 结构），让其他容器针对性读，不必全读。
