---
name: ima-zip-migrate
description: 从 IMA 知识库下载 zip 迁移包并安全解压落位到本地工作区（跨机迁移场景）。当需要「从 IMA 共享库取 zip → 下载 → 解压到目标目录 → 校验结构 → 回填进度回执」时使用。触发词：迁移包、zip 落地、从 IMA 下载压缩包、跨机迁移解压、记忆资产包。
agent_created: true
---

# IMA zip 迁移包下载与安全解压

跨机器迁移（Mac 主分身 → Windows 分身）的标准落地链路。源侧把资产按**目标目录结构**打包 zip 传 IMA 共享库，本侧下载解压即落位。

## 适用前提

- 源侧打包时**按目标目录结构**，禁止平铺（平铺需本侧手工映射，易错易漏）。
- 隐藏目录（如 `.workbuddy/skills/xxx/`）需源侧确认保留层级，不能只压叶子文件。

## 执行链路

### 1. 定位 media_id

```bash
NODE="<工作目录>"
IMA="<工作目录>"

"$NODE" "$IMA" "openapi/wiki/v1/get_knowledge_list" \
  '{"knowledge_base_id":"<kb_id>","cursor":"","limit":50}'
```

在 `knowledge_list` 里按 `title` 匹配 zip 文件名，取其 `media_id`（zip 的 `media_type=14`，且 media_id 前缀是 `xmind_` — 这是 IMA 内部归类，不代表文件是 xmind，不要因此判错）。

### 2. 取签名下载链接

```bash
"$NODE" "$IMA" "openapi/wiki/v1/get_media_info" '{"media_id":"<media_id>"}'
```

返回 `data.url_info.url` + `data.url_info.headers`。**headers 必须原样带上**，否则 403。链接有时效，取到就立刻下载。

### 3. Node 下载二进制

用 `scripts/download_zip.cjs`（本 skill 附带）：

```bash
"$NODE" <skill_dir>/scripts/download_zip.cjs "<url>" "migrate.zip" '<headers_json>'
```

不用 curl / PowerShell —— PowerShell 常被沙箱拦，curl 传中文 header/URL 参数易出转义坑。输出 `{"ok":true,"bytes":N}`。

### 4. 先 list，后 extract（冲突预扫）

```bash
PY="<工作目录>"
"$PY" <skill_dir>/scripts/zip_tool.py migrate.zip list                 # 只看结构
"$PY" <skill_dir>/scripts/zip_tool.py migrate.zip extract "<目标目录>"   # 落位
```

`zip_tool.py` 已内置四条保护：

1. **中文文件名安全** — 无 UTF-8 flag 时自动 cp437→utf-8 回退，绕开 git bash 中文乱码。
2. **绝不覆盖** — 目标已存在同名文件即跳过并记入 `conflicts`，符合迁移红线「保留本机现版」。
3. **过滤 Mac 垃圾** — `__MACOSX/`、`.DS_Store`、`Thumbs.db`。
4. **原样保真** — 不重命名、不转码。

### 5. 校验

```bash
"$PY" -c "import zipfile;print(zipfile.ZipFile('migrate.zip').testzip())"   # None = CRC 全通过
```

再逐项比对落地文件 vs 需求清单（P0/P1/P2 各几项、有无缺项多余项），抽查文本文件头部与二进制 magic number。

### 6. 回填进度回执

把清单表的状态列改成 `[x] 已落位` + 字节数，并追加一段执行记录（下载字节数 / CRC 结果 / 冲突数 / 结构校验结论 / 观察项）。

## 坑与判据

| 现象 | 判断 |
|---|---|
| zip 的 media_id 前缀是 `xmind_` | 正常，IMA 内部归类，非文件类型错误 |
| `head -c N` 看中文文件尾部有乱码字符 | 是字节截断多字节字符，**不是**文件损坏；以 CRC 和 Read 工具为准 |
| 图片 magic number 与扩展名不符（如 .png 实为 JFIF） | 若 CRC 通过 = 源文件本来如此，**保持原样不改名**，只记为观察项 |
| 下载 403 | headers 没带全，或链接过期 → 重新 `get_media_info` |

## 落地后必做

迁移包内的 HANDOFF / dossier 类文档常含**源机器绝对路径**（如 `<工作目录>`），在目标机是失效引用。按红线**不擅自改写**，作为观察项上报，由用户决定是否出路径映射版。
