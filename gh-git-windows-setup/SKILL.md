---
name: gh-git-windows-setup
description: >-
  Bring up working GitHub read+write access (gh CLI auth + a usable git) on a
  locked-down Windows box that ships only a slimmed-down PortableGit. Use when:
  `git clone` fails with "remote helper 'https' aborted session"; GitHub push/pull
  needs credentials; the user wants a resident-PC agent to pull code from GitHub
  and push fixes back; or `gh` is missing / not authenticated. Encapsulates the
  npmmirror download switch, the SHA256 verification, the GitHub device-flow
  auth without an interactive TTY, the SSH-22 fallback that bypasses a floating
  outbound-NAT proxy (the "proxy IP drifts / Malaysia exit" case where HTTPS
  push dies at POST with schannel `missing close_notify` / exit 128), and the
  PowerShell traps that silently break every .ps1 in this environment.
agent_created: true
---

# GitHub read+write on a locked-down Windows box

Two independent things must both work before `git clone` / `git push` succeed:

1. **Credentials** — a token with `repo` scope, persisted where `git` can read it.
2. **A git binary with a working HTTPS transport** — the network-facing
   `git-remote-https.exe` must actually run.

On the <本机> (Windows / `<USER>`) *both* were broken. This skill records how each
was fixed and the traps that made it take 7 attempts.

## Default launch path（默认启动指令）

本 skill 被触发时，**先判定卡点类型再选分支**，不要无脑走完整 HTTPS 链路：

- **分支 A — 浮动代理 / 代理中段（默认优先判定）**：出现任一信号即跳到 Step 6 走 SSH 22 直连，跳过 Step 3–5 的 HTTPS 试错：
  - `git push` over HTTPS 在 advertisement 之后、**POST 前静默失败、exit code 128、无 fatal**；
  - 报错含 `schannel: server closed abruptly (missing close_notify)`；
  - 用户提及「代理飘 / 浮动代理 / VPN 出口 NAT / 授权页闪过海外（马来西亚等）IP」。
- **分支 B — 真·HTTPS 链路缺失**：git 没有 `git-remote-https.exe`、gh 未登录、缺凭据 → 走 Step 1–5。
- **分支 C — 两者都要**：先 Step 2 拿 gh token（备用），再 Step 6 走 SSH。

原理（也是分支 A 直接赢的原因）：浮动代理 = 出口 NAT，本机所有走 HTTP 代理的出站 HTTPS 都从轮换海外节点出去，代理在 TLS 层重签/中段，本机 schannel / openssl 握手对不上 → push 中段。SSH 22 是**原始 TCP、不经本机 HTTP 代理**，端到端加密，代理 intercept 不到。实战（`<示例项目>` N4）正是此场景：HTTPS 试错多轮全败、切 SSH 一次过。

## When to use

- `git clone https://...` → `remote helper 'https' aborted session`.
- The machine has a `PortableGit` under `.workbuddy\binaries\` that is far smaller
  than a real Git for Windows install (~130 MB vs ~350 MB).
- `gh auth status` says not logged in, or `gh` is not on PATH at all.
- Evidence to collect first: `git --version`, `git --exec-path`, and whether
  `git-remote-https.exe` exists **inside** the directory `--exec-path` reports.

## Procedure

### Step 1 — probe before touching anything

```powershell
# git present? which one? where does it look for helpers?
& "<gitDir>\cmd\git.exe" --version
& "<gitDir>\cmd\git.exe" --exec-path
Get-ChildItem ( & "<gitDir>\cmd\git.exe" --exec-path ) -Filter "git-remote-ht*"
```

If `git-remote-https.exe` is NOT inside the `--exec-path` directory, the install is
a trimmed build and HTTPS transfers will fail no matter how you set `PATH`.
Do not spend time on `GIT_EXEC_PATH` / copying DLLs — replace the install (Step 3).

### Step 2 — install + authenticate gh CLI

`gh` is a single binary; install it portable, never system-wide (no registry, no
UAC, revertible by deleting a folder):

- Download `gh_<ver>_windows_amd64.zip` from `cli/cli` releases into
  `~/.workbuddy\binaries\gh\`, extract, expect
  `...\bin\gh.exe`.

**Do NOT use `gh auth login --web` from a script.** In a non-TTY/`Start-Process`
context gh detects no terminal and produces no output at all — it just hangs.
Drive the same device flow over plain HTTP instead:

1. `POST https://github.com/login/device/code` with
   `client_id=178c6fc778ccc68e1d6a` (the public gh CLI client id) and
   `scope=repo workflow gist read:org` → returns `device_code`, `user_code`,
   `verification_uri` (`https://github.com/login/device`), `interval`.
2. Surface `user_code` + `verification_uri` to the human verbatim; they must open
   the URL, sign in, paste the code, and click Authorize.
3. Poll `POST https://github.com/login/oauth/access_token` every `interval`
   seconds until `access_token` appears (Grant type: device code — include
   `device_code` and `grant_type=urn:ietf:params:oauth:grant-type:device_code`).
4. Persist it: `gh auth login --with-token` reading the token from stdin.
5. Verify: `gh auth status` and `gh api user --jq .login` must both report the
   expected account. Also confirm the token scope actually contains `repo`.

### Step 3 — install the FULL PortableGit (the actual fix for HTTPS)

The bundled slim PortableGit cannot run its HTTPS helper, so download the real one.
**GitHub release downloads are unusable here (~25 KB/s). Use the npmmirror mirror —
same official bytes, ~5.7 MB/s, measured 220x faster.**

```powershell
$tag = "v2.55.0.windows.5"      # or take the latest from the GitHub API
$url = "https://registry.npmmirror.com/-/binary/git-for-windows/$tag/PortableGit-<VERSION>-64-bit.7z.exe"
curl.exe -L -s -o "$env:TEMP\PortableGit-setup.exe" $url
```

Verify integrity against the **official** hash (GitHub's release body carries a
markdown table of `<asset> | <sha256>`):

```powershell
$rel = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest" `
    -Headers @{ "User-Agent" = "probe" }
($rel.body -split "`n" | Where-Object { $_ -match "PortableGit-2\.55\.0\.5-64-bit\.7z\.exe" })
(Get-FileHash "$env:TEMP\PortableGit-setup.exe" -Algorithm SHA256).Hash
```

Expect `58,960,208` bytes and
`5aa8a20f6e9abb2c755f0e73c91c687701a46b309ad84a0ca6509380fa4ae290`.

Extract the self-extracting 7z (`-o<dir>` and `-y` are 7z switch syntax):

```powershell
$dest = "~/.workbuddy\binaries\PortableGit-full"
New-Item -ItemType Directory -Force $dest | Out-Null
Start-Process -FilePath "$env:TEMP\PortableGit-setup.exe" `
    -ArgumentList @("-o$dest", "-y") -NoNewWindow -Wait
```

Takes ~63 s. Afterwards `$dest\mingw64\libexec\git-core\git-remote-https.exe`
exists and `git --exec-path` points straight at it.

### Step 4 — wire gh's token into git

```powershell
$git = "$dest\cmd\git.exe"
& "$ghDir\bin\gh.exe" auth setup-git
```

This writes to `<HOME>\.gitconfig`:

```
credential."https://github.com".helper = !'<ghDir>\bin\gh.exe' auth git-credential
credential."https://gist.github.com".helper = !'<ghDir>\bin\gh.exe' auth git-credential
```

Note it is **host-keyed** (`credential.https://github.com.helper`), not the bare
`credential.helper` key — checking the wrong key makes it look like it silently
did nothing. To revert, delete those lines.

Always prepend the new git to `PATH` in the same shell, since scripts call `git`
by bare name: `$env:PATH = "$dest\cmd;$dest\mingw64\bin;$env:PATH"`.

### Step 5 — verify read AND write (do not stop at clone)

```powershell
# read
if (Test-Path "$repo\.git") { <move it aside> }   # see pitfalls
& $git clone https://github.com/<owner>/<name>.git $repo
& $git -C $repo rev-parse HEAD
& $git -C $repo ls-remote origin main   # must equal the local HEAD sha

# write - real push on a throwaway branch, then delete it
& $git -C $repo checkout -b ccs-write-probe-<date>
<write a file>
& $git -C $repo -c "user.name=probe" -c "user.email=probe@local.invalid" `
    add <file>; and commit -m "..."
& $git -C $repo push origin "refs/heads/<probe>:refs/heads/<probe>"
& $git -C $repo ls-remote origin refs/heads/<probe>     # remote must show it
& $git -C $repo push origin --delete <probe>
& $git -C $repo ls-remote origin refs/heads/<probe>     # must be empty
& $git -C $repo checkout main; and branch -D <probe>
```

Confirming the ref on the remote via `ls-remote` (a separate round trip) is the
proof — a local `commit` alone proves nothing about remote write access.
Pass commit identity via `-c` so the global git config stays untouched.
Never push a probe onto `main`; create and delete a branch instead.

### Step 6 — SSH 22 直连（绕过浮动代理 / 代理中段 HTTPS）【分支 A 执行路径】

前置诊断（只读，确认 22 直连可达，不经 HTTP 代理）：

```powershell
# 原始 TCP 22 是否通（直接出网，不经本机 HTTP 代理）
$t22 = Test-NetConnection github.com -Port 22 -WarningAction SilentlyContinue
Write-Output ("github.com:22 TcpTestSucceeded=" + $t22.TcpTestSucceeded)
# SSH 服务可达性（应回 Permission denied (publickey)，即连上但无密钥）
& "C:\WINDOWS\System32\OpenSSH\ssh.exe" -T -o BatchMode=yes -o ConnectTimeout=15 `
    -o StrictHostKeyChecking=no git@github.com 2>&1
```

两处都 `True` / `Permission denied (publickey)` → 通道成立，直接走 SSH。

生成 ED25519 密钥（只写本地 `%USERPROFILE%\.ssh`，可逆、无外部副作用）：

```powershell
$keygen = "C:\WINDOWS\System32\OpenSSH\ssh-keygen.exe"
# 用 --% 停止 PowerShell 解析令牌，避免 -N "" 空口令被吞成 "Too many arguments"
& $keygen --% -t ed25519 -f <HOME>\.ssh\id_ed25519 -N "" -C CCS@<HOSTNAME>
# 收敛私钥权限：仅当前用户可读
icacls <HOME>\.ssh\id_ed25519 /inheritance:r /grant:r "$env:USERNAME:(R)"
# 取出公钥待注册
Get-Content <HOME>\.ssh\id_ed25519.pub
```

注册公钥（**默认走人工贴**：本机 gh 输出在 PowerShell 常被吞、且 token 未必带 `admin:public_key` scope，自动注册不可靠）：

1. 浏览器开 `https://github.com/settings/ssh/new`，Title 填 `WIN-CCS`（或好认名），Key type 保持 `Authentication Key`。
2. 把 `id_ed25519.pub` 整行粘入 Key 框 → `Add SSH key`。
3. 用户回「已加好」后再推进（**不擅自动外部账户**）。

切 remote + push（**git 路径必须用 `C:/Users/...` Windows 风格，不是 `/c/Users/...`**，后者被 git 当字面路径失败）：

```powershell
$git = "~/.workbuddy\binaries\PortableGit-full\mingw64\bin\git.exe"
# 复核认证（预期 Hi <owner>! ... successfully authenticated）
& "C:\WINDOWS\System32\OpenSSH\ssh.exe" -T git@github.com 2>&1
# 切 remote 到 SSH（换成你的 owner/repo）
& $git -C "<HOME>\<示例项目>" remote set-url origin git@github.com:<GITHUB_USER>/<示例项目>.git
& $git -C "<HOME>\<示例项目>" remote -v
# push（走 22 直连，不经 HTTP 代理）
& $git -C "<HOME>\<示例项目>" push origin main 2>&1
```

成功标志：`To github.com:<GITHUB_USER>/<示例项目>.git` + `main -> main`。

## Pitfalls (each one cost a failed round)

- **PowerShell 5.1 reads BOM-less UTF-8 `.ps1` as ANSI/GBK.** Chinese comments
  swallow the following newline, `@(...)` arrays break, and **the entire script
  runs zero lines** — no log, no output file, exit code still 0. **Write every
  `.ps1` in pure ASCII.** This is the single highest-value rule here.
- **`Start-Process -ArgumentList` does not quote array elements containing
  spaces.** `"-w", "HTTP=%{http_code} BYTES=%{size_download}"` reaches the child
  as four separate argv entries, so curl treats the trailing pieces as extra URLs
  and writes the real payload to wherever stdout was redirected. Use
  `--write-out=X` / `--flag=value` forms with no spaces, or call the binary with
  `&` instead of `Start-Process`.
- **Background PowerShell tasks are killed at roughly 2 minutes** (`failed`,
  no output). Anything longer must run in the foreground, be split into chunks, or
  use a mechanism outside the shell.
- **The PowerShell tool often returns empty stdout.** Always have scripts write
  results to a file under `$env:TEMP` and read that file back.
- **Do not invoke `powershell.exe` from the Bash tool** — it is blocked by policy
  ("Invoking PowerShell from Bash bypasses PowerShell security checks"). Use the
  PowerShell tool for PowerShell, Bash for POSIX.
- **`git clone` into a directory that already holds an empty `.git`** succeeds in
  reporting failure: git says the branch "does not have any commits yet" and your
  verification step silently passes over an empty tree. Always check for and move
  aside a stale target first (rename rather than delete — deletes are sometimes
  blocked in the sandbox).
- **`Invoke-RestMethod` against GitHub needs an explicit `User-Agent` header** or
  the API rejects the call.
- `git log` output shows mojibake for Chinese commit subjects in these consoles —
  that is a console encoding artifact, not repository corruption.
- **git (Windows 版) 把 `/c/Users/...` 当字面路径失败** —— 在 PowerShell 调用 git 时一律用
  `C:/Users/...`（正斜杠 Windows 风格）或 `C:\Users\...`，不要写 Unix 风格 `/c/Users/...`。
- **本机 Bash 工具 coreutils 缺失**（`ls`/`cat`/`mkdir`/`dirname` 全 `command not found`、
  exit 127）—— 文件/命令操作用 PowerShell；gh 子进程输出在 PowerShell 常被吞 → 落
  `$env:TEMP` 文件再 Read，且 PS5.1 `>` 默认 UTF-16 会被 Read 误判二进制，用
  `Out-File -Encoding ascii` 或 `2>&1 | Out-String` 落盘。

## Reusable scripts

Working, re-runnable versions of every step live in
`<PROJECT_ROOT>`:
`install-gh-cli.ps1`, `gh-device-flow.ps1`, `dl-speed-probe.ps1`,
`git-full-run2.ps1` (download+extract+wire+clone), `git-clone-final.ps1`,
`git-write-probe.ps1`.
