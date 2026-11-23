# 两腿详细对比与踩坑记录

> 本文件是速查层；完整 SOP 真源在主工程容器：
> - `SOP/诚通网盘书源扒取runbook.md`
> - `SOP/智能小程序书源扒取runbook.md`
> 改细节去真源改，本文件不维护第二份。

## 一、两腿对比（2026-10-17 实测）

| 维度 | 诚通腿（优先） | 百度腿（兜底） |
|---|---|---|
| 上游 | GitHub 仓库文本索引（curl 可 grep） | 百度智能小程序 AI 对话（JS 渲染黑盒） |
| 找书方式 | 索引 md 里 grep 书名 | 对话链接改 `_chatQuery` 参数，渲染后看回复 |
| 传输 | 纯 HTTP 两个 API，免登录免 cookie | 无头浏览器渲染 + bdpan 转存下载 |
| 产物格式 | epub/mobi/azw3 三格式（zip 打包） | 单一 PDF |
| 速度 | 约 1 分钟/本（30-50KB/s 限速） | 2-3 分钟/本（渲染 + 转存） |
| 规模化的坑 | 直链 2 小时有效、限速 | 小程序 token 会过期、百度风控 |
| 失败模式 | 错提取码→423、错 fid→403 | token 过期→空壳、书不在库→答非所问 |

## 二、诚通腿 API 细节（排障用）

分享链：`https://url89.ctfile.com/f/<fid>?p=<提取码>`

1. `GET https://urlapi.ctfile.com/api/v2/resource?kind=file&id=<fid>&folder_id=0&fk=&passcode=<pwd>&type_id=0`（带 `Referer: https://url89.ctfile.com/`）→ 返回 file_name / file_chk / verifycode / file_size_bytes / file_id / userid / start_time / wait_seconds；
2. `POST https://urlapi.ctfile.com/api/v2/download`（JSON）body＝`{context:{kind,id,folder_id,fk,passcode,type_id}, mb:false, app:false, verifycode, original_file:{file_id,userid,file_chk,start_time,wait_seconds}}` → 返回 `data.downurl` 直链；
3. `GET downurl`（带 Referer）→ zip 落盘。

`scripts/ctfile_fetch.py` 已封装三步；`wait_seconds` 是非会员等待（免费通道排队），脚本已处理。

## 三、选用裁决全文（2026-10-17 甘问「合并还是两腿」）

**保持两条腿，使用界面合成一条（诚通优先、百度兜底），代码不合并。**

- 代码层无物可合：上游/下游/产物全不同，硬包统一入口＝抽象处处泄漏＝布满 if-else 的壳；
- 源必须复数：诚通没有的书百度生态可能有，百度 token 死那天诚通照样跑——冗余的是源不是代码；
- 诚通实证占优：免登录、索引可 grep、三格式、更快。百度价值在「诚通索引没有」和「PDF 形态更清晰时」。

## 四、失败分支

| 症状 | 判读 | 处置 |
|---|---|---|
| 诚通 resource 返回 423 | 提取码错 | 统一码 `8866`，检查链接 p= 参数 |
| 诚通 resource 返回 403 | fid 错/链失效 | 回索引重新 grep 取链 |
| 直链下载中断/超时 | 限速或直链过期 | 重跑 `ctfile_fetch.py`（幂等） |
| 百度腿渲染超时 | 代理/VPN 出口问题 | Chrome 需显式 `--proxy-server`（curl 走 env 代理、Chrome 不读 env） |
| 小程序答「未找到」 | 书不在库里 | 登记缺口，转 PDF 直下渠道 |
| token 失效/页面空壳 | 小程序 token 过期 | 找甘在微信重新打开小程序分享新链 |
| 诚通仓库 404/DMCA | 上游索引死了 | 触发重新审视：百度升主力，结构不变 |

## 五、已踩坑（本机环境相关，会复犯）

1. **Bash 工具里的 grep 不认 `\|` 交替**——正则搜索一律用专用 Grep 工具，禁 Bash grep（已连犯多次）；
2. **macOS 自带 unzip 6.00 没有 `-O` 参数**——GBK 文件名解压用 Python zipfile，不用 unzip -O；
3. **Chrome 不读 env 里的代理变量**——curl 能通而 Chrome 超时时，给 launch args 加 `--proxy-server=<代理地址>`（本机代理从 `env | grep -i proxy` 取）；
4. **Bash grep 交替符、Python f-string 里写中文注释进字节字面量**——都会炸，写代码时避开。

## 六、库内规范形态

- 三格式书：`books/_source/<池子>/<书名> 全格式/<书名>.{epub,mobi,azw3}`；
- PDF：`books/_source/<池子>/<书名>.pdf` 平铺；
- 池子目录：`masspool-healing/`（大众池·疗愈向）、甘的池子（AI 实操）按蒸馏主线书单走；
- 每落地一本，在 `内容产出清单_持续维护.md` 或对应书单件登记（可溯：书名→源链→落盘路径）。
