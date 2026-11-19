---
name: mac-universal-bundle-verify
description: macOS universal(.app) 或任何 fat Mach-O 包在发布/交付给他人前的核验清单——覆盖「cargo tauri build 不签名」这个必踩坑、切片级架构核验（不靠 lipo 自报）、依赖库/符号/ABI 差异判读、以及如何用源码层扫描把「跨架构风险」从『不知道』量化成『只差运行时确认』。当需要 bbuild/交付 macOS 双架构包、怀疑包是否真含某个功能、或要回答『这包在别人的 Mac 上能不能跑』时使用。触发词：universal 包核验、双架构、lipo、fat binary、.app 签名、release 包验证、能不能在 M 芯片跑。
agent_created: true
---

# macOS Universal 包 · 发布前核验清单

## 何时用

- 跑完 `cargo tauri build --target universal-apple-darwin`（或任何产 fat Mach-O 的打包），准备把 `.app` 交付给别人
- 要回答「这个包在别人的机器上能不能跑」「arm64 那半边行不行」这类问题
- 怀疑某个新功能到底进没进 release 包

## 铁律一：`cargo tauri build` 全程不签名（最大的坑）

**症状**：`codesign -dv <app>` 报 `code object is not signed at all` —— 不是签了个空的，是**完全没签**。

**判据链**：
```bash
codesign -dv --verbose=2 "X.app" 2>&1 | head -6
```
若输出 `code object is not signed at all` → 包不可交付。Gatekeeper 第一关就挂。

**为什么容易漏**：老包可能**有**签名（前一次手工补的），于是你会以为打包流程自带签名。实则 `cargo tauri build` 只在配置了签名身份时才签；adhoc 也得手工。

**修法**（在目标位置签，不要在源 bundle 签完再拷——拷的过程可能丢签名/xattr）：
```bash
codesign --force --sign - "X.app"                     # -  = adhoc
codesign --verify --deep --strict --verbose=2 "X.app" # 必须 rc=0
```
期望看到 `valid on disk` + `satisfies its Designated Requirement`。

## 铁律二：落位走「零删除路径」

如果目标位置已有一个旧包（且用户可能正在用它），**不要 `rm -rf` 再拷**：

```bash
ditto "新包.app" "目标.app"          # 保留 xattr / 资源叉；只覆盖，不删目标多余文件
codesign --force --sign - "目标.app" # --force 会重建 _CodeSignature
```

⚠️ **`ditto` 不删目标的多余文件** → 若旧包有 `Contents/_CodeSignature` 而新包没有，会**残留旧签名** → 必须靠 `codesign --force` 重建覆盖。

⚠️ **动包前先确认用户实例已退出**，并**先做兜底备份**（`cp -R 旧包 旧包_M<n>封板.app`），备份后**核 sha256 与旧包逐字节相同**才算备份有效。

⚠️ **`ditto` 后父目录 mtime 可能不变**（只改文件内容不改目录条目时）→ **不要用目录 mtime 判断"换没换"**，看文件级 `stat -f %z,%Sm` + sha256。

## 核验清单（逐条跑，别跳）

### 1. 架构 —— 走两条独立通道

```bash
lipo -info "X.app/Contents/MacOS/<bin>"     # 通道①：lipo 自报
```
```python
# 通道②：直读 Mach-O 头（不依赖 lipo，防它自报有误）
d = open(bin, "rb").read()
print(d[:4].hex())          # cafebabe = fat/universal ; cffaedfe = thin x86_64 ; cffaedfe/... 
# fat 头后 4 字节 = 架构数；再逐条读 cpu type
# 0x1000007 = x86_64 ; 0x100000c = arm64
```

### 2. 切片级核验（要回答"arm64 行不行"就必须做这步）

```bash
lipo -thin arm64  bin -output /tmp/slicing.arm64
lipo -thin x86_64 bin -output /tmp/slicing.x86_64
file /tmp/slicing.*
```

**依赖库逐行对照**（两边应完全相同；出现差异就是风险）：
```bash
otool -L /tmp/slicing.arm64
otool -L /tmp/slicing.x86_64
# 关键：搜 @rpath / @loader_path / 外部绝对路径 —— 有 = 可能在别人机器缺库
otool -L /tmp/slicing.arm64 | grep -E "@rpath|@loader_path|/Users/|/opt/|/usr/local/"
```
理想结果：全是 `/System/Library` + `/usr/lib`，**零非系统依赖**。

**平台与最低系统版本**：
```bash
otool -l /tmp/slicing.arm64 | grep -A6 LC_BUILD_VERSION      # 新式（arm64 用）
otool -l /tmp/slicing.x86_64 | grep -A5 LC_VERSION_MIN_MACOSX # 旧式（x86_64 可能用）
```
- arm64 在 macOS 11 才出现 → 必然用新式 `LC_BUILD_VERSION`，`platform 1` = macOS
- x86_64 可能仍是旧式 `LC_VERSION_MIN_MACOSX` —— **这是链接器对两架构的正常差异，不是缺陷**
- 判据：两边 `minos` 都 ≤ 接收方系统版本即可

### 3. 符号差异 —— 差别要能逐个解释，不许留未解释项

```bash
nm -u arm64.bin  | awk '{print $NF}' | sort -u > /tmp/s_arm64.txt
nm -u x86.bin    | awk '{print $NF}' | sort -u > /tmp/s_x86.txt
comm -23 /tmp/s_arm64.txt /tmp/s_x86.txt   # 只 arm64 有
comm -13 /tmp/s_arm64.txt /tmp/s_x86.txt   # 只 x86_64 有
```

**已知的正常 ABI 变体**（出现它们是健康的，不是 bug）：

| x86_64 侧 | arm64 侧 | 原因 |
|---|---|---|
| `_stat$INODE64` / `_fstat$INODE64` / `_lstat$INODE64` / `_opendir$INODE64` / `_readdir_r$INODE64` | `_stat` 等无后缀 | inode64 后缀是 x86_64 的历史兼容变体；arm64 纯 64 位不需要 |
| `_objc_msgSend_stret` | （无） | x86_64 结构体返回值走独立入口；arm64 统一调用约定后取消 |
| `___bzero` | `_bzero` | 符号命名差异 |
| `_close$NOCANCEL` | `_close` | 变体后缀 |

同时数一下总数（如 351 vs 352）——**差一两个属正常，但要能指名道姓解释是哪一个**。

### 4. 签名覆盖两个切片

```bash
codesign --verify --strict --verbose=2 --arch arm64  "X.app"   # rc 应为 0
codesign --verify --strict --verbose=2 --arch x86_64 "X.app"   # rc 应为 0
```

### 5. 「新功能真进包了吗」—— 字符串核验

**挑功能独有的中文字符串常量**（release 优化会删掉纯内部函数名，但**界面文案/serde 字段名/命令名是字符串常量，必然保留**）：

```python
d = open(bin, "rb").read()
for s in ["功能独有的中文文案", "另一个独有文案"]:
    print(s, d.find(s.encode("utf-8")))
```

**必须带负对照**：用**旧包**跑同一份清单 → 旧包应 **0 命中**。再放一两条**两包共有**的老字符串（如主界面标题）→ 应两边都命中。三者齐了才证明**是"真没有"，不是"搜法不对"**。

⚠️ 若某条字符串在新包也缺失：先查它是否落在 `#[cfg(debug_assertions)]` 里 —— **冒烟/调试钩子在 release 下会被 DCE**，字符串消失是**设计要求不是缺陷**。但由此可推出一条须标注的事实：**release 包里那个冒烟环境变量是死开关**。

### 6. ★ 把「跨架构风险」量化（最有价值的一步）

上面几条只能证"结构自洽"。真正决定风险的是**两切片代码路径是否相同**：

```bash
grep -rnE "target_arch|target_pointer_width" src/     # 零命中 = 无架构分支
grep -rnE "as u32|as i32|usize as|mem::transmute" src/ # 零命中 = 无指针宽度假设
grep -rn "target_os" src/                              # 有也无妨：两切片都是 macOS → 走同一支
```

**判读**：
- 零 `target_arch` + 零指针宽度假设 ⇒ 两切片走 **100% 相同代码路径**，唯一差异来自编译器后端
- ⇒ 风险从「编译/链接都可能不对」**降级为「只差运行时确认」**
- 这让你能对用户说清**风险有多大**，而不是干说"不确定"

## 在哪台机器上能验什么（物理边界，先认清再排工）

**硬事实：Intel Mac 无法执行 arm64 二进制。** Rosetta 2 是**单向**的——只在 Apple Silicon 上把 x86_64 翻译成 arm64，**反向不存在**，也没有可用的模拟层。所以在 Intel 机上，`aarch64-apple-darwin` 切片**只能静态核验（看），不能运行（跑）**。别指望"脚本/工具"在 Intel 上跑 arm64 —— 没有这种东西。

| 验证项 | Intel 本机 | CI（arm64 runner） | 借/自有 M 系真机 |
|---|---|---|---|
| 交叉编译 fat binary | ✅ | ✅ | ✅ |
| 静态核验（本清单 1–6 项） | ✅ | ✅ | ✅ |
| **arm64 真跑，会不会崩** | ❌ | ✅ | ✅ |
| **GUI 行为**（托盘 / 热键 / 焦点归还） | ❌ | ❌ **无交互桌面** | ✅ |

**CI 的真相**（GitHub Docs 运行器参考）：`macos-latest` / `macos-14` / `macos-15` / `macos-26` = **arm64（M1，3 核 / 7 GB）**；`macos-15-intel` / `macos-26-intel` = Intel x64。公开仓库标准 runner 免费不限量；私有仓消耗额度、macOS 倍率高于 Linux。arm64 runner **无静态 UDID**、不支持嵌套虚拟化。

⚠️ **决策判据**：**如果产品本体是 GUI**（托盘程序、菜单栏 App、含全局热键的工具），CI 能补的那一格价值趋近于零——它抓得到"启动即崩"，抓不到"托盘是个空白方块"。此时**为 CI 建 workflow 不值得**，改走「借一台 M 系真机人工过一遍」。反过来，纯 CLI / 后台服务 → CI 完全够用。

## 借 M 系真机验收（五分钟单，不安装不留痕）

别在别人机器上做工程，做一次**走到就完**的验收：

```bash
# ① 先验真身，别借到 Intel 白跑
uname -m; sysctl -n hw.model; sw_vers -productVersion   # uname -m 必须是 arm64

# ② 静态三查（.app 直接跑，别拖进 Applications）
xattr -dr com.apple.quarantine /路径/X.app                    # 传输会带隔离属性，不解双击必被拦
lipo -archs /路径/X.app/Contents/MacOS/x                      # 必须含 arm64
codesign --verify --deep --strict -vvv /路径/X.app; spctl -a -t exec -vvv /路径/X.app
```

③ **人眼三格**（这才是来这一趟的理由）：托盘图标是否显示正确（Tauri 对图标尺寸/template 敏感）／全局热键能否注册、冲突时是否静默失败／切出去再切回来焦点是否归还。走完删掉拷进去的东西。顺带可把「新 macOS 版本兼容性」一并验了。

⚠️ **崩了先别怪代码**：交叉编译出的包若在真机崩，先排除"交叉编译的锅"——**借到的若是带 Xcode + rust 的开发机，在那台上原生 `cargo tauri build` 一次做对照最干净**。

## 结论怎么下（措辞纪律）

**编译正确 ≠ 运行正确。** 无论上面查到多齐，只要没在真机上跑过，就必须说：

- ✅ 可断言：架构齐全 / 依赖自洽 / 签名有效 / 新功能内容在包里 / 两切片代码路径一致
- ❌ 不可断言：**运行时行为**（热键注册 / WebView 渲染 / 托盘图标等系统交互路径）
- 若手头机器架构 ≠ 目标架构（如 Intel 机验 arm64）：**必须标「未验证」并要求接收方回报**，别用"大概率没问题"顶替

给接收方的**一分钟自检**（写进交付说明）：
```bash
lipo -info /Applications/X.app/Contents/MacOS/x   # 看架构
/Applications/X.app/Contents/MacOS/x              # 终端直跑，看有无 Bad CPU type / crash
```

## 常见误判速查

| 表象 | 真相 |
|---|---|
| 老包有 `_CodeSignature` | 那是上次手工签的，不代表这次会签 |
| 目录 mtime 没变 | `ditto`/`codesign` 只改内容不改目录条目时正常 |
| `read_configured_xxx` 搜不到 | 纯内部函数名，release 会掉；换字符串常量判据 |
| 符号数差 1 个 | 正常，但要指名是哪个 ABI 变体 |
| `lipo -info` 说双架构 | 仍需独立复核（读 Mach-O 头），别单信工具自报 |
