---
name: web-ui-click-harness
description: 用 Chrome headless + 离线 harness「派发真实 click」端到端验证网页交互（点选/弹框/状态回显），并带红绿负控制。当出现「脚本全绿但真机点了没反应」「交互类 bug 抓不到」「前端验收靠肉眼」时用。触发词：真实点击验证、click 回路、harness、前端交互验收、能红能绿。
agent_created: true
---

# web-ui-click-harness —— 前端交互的「能红能绿」回路

## 何时用

- 用户报「点了没反应 / 没生效 / 弹框不弹」这类**交互** bug。
- 你要改的是**选择器 / 事件绑定 / 状态回显**附近的东西。
- 你已经有一堆**函数级**单测（直接调 `foo()`），但它们全绿而真机不对。

> 兄弟 skill：**渲染一致性 / 多宿主同源**（编辑面 Shadow DOM vs 预览 vs 导出、「看起来一样但其实不同源」）不属本 skill，见 **`render-parity-check`**。本 skill 管「点了有没有反应」，它管「渲染出来是不是同一个东西」。

## 铁律（为什么函数级验证不够）

函数级验证会漏掉**整条链路中非函数的部分**：选择器命中、事件派发、DOM 可见性、CSS 计算值。

真实案例（贴图号编辑器项目）：`applyRole()` / `toggleKey()` 直接被调用时全绿，
但真实点击时 **`closest()` 选择器不含 `<span>`** → 点署名什么都没选中 → 功能全链失效。
**函数级测试永远发现不了这个 bug。**

## 配方

### 1. 由真实页面生成 harness（别手写一个模拟页）

```python
idx = open("public/index.html", encoding="utf-8").read()
idx = idx.replace('<script src="/static/app.js"></script>', '<script src="app.js"></script>')
```

手写模拟页 = 又一层失真的模仿；由**真页面**改路径引用才是同一个 DOM/CSS。

### 2. 内联「服务端才给」的资源 + 覆写 fetch

前端若在运行时 `fetch` 拿 CSS/配置，`file://` 下会静默失败 → **CSS 缺失 → 所有计算值退化** →
任何「按尺寸/档位/可见性判断」的断言都失真（假绿或假红）。

```html
<style type="text/plain" id="cssmap-editorial">…同源 CSS…</style>
<script>
(function(){ var M={editorial: document.getElementById('cssmap-editorial').textContent};
  var real = window.fetch;
  window.fetch = function(u){
    var m=/style\?style=([a-z]+)/.exec(String(u));
    if(m&&M[m[1]]) return Promise.resolve({ok:true,text:function(){return Promise.resolve(M[m[1]]);}});
    return real ? real.apply(this,arguments) : Promise.reject(new Error('no fetch')); };
})();
</script>
```

**大段 CSS 不要经 `json.dumps` 内联成 JS 字符串字面量** —— 实测会让**整块页面脚本不执行**
（`#out` 空、连 `window.onerror` 都收不到）。用 `<style id>` 承载、JS 里读 `textContent` 才是稳的。

### 3. 派发真实事件，不调函数

```js
const click = (el) => el.dispatchEvent(new MouseEvent("click", {bubbles:true, cancelable:true}));
click(sh.querySelector("[data-sig]"));      // 真实 click，走 addEventListener 链路
click(roleBtn("正文"));                      // 真按钮的 click
```

拦 `confirm` 拿证据（别真弹窗）：

```js
window.confirm = function(m){ MSGS.push(String(m)); return false; };  // 一律取消 → 可判「弹过没」且不改状态
```

「找不到元素」本身是症状 → 用**软点击**记录落空，别抛异常中断回路：

```js
function clickSoft(el, what){ if(!el){ R.misses.push(what); return false; } click(el); return true; }
```

### 4. 抓状态快照（快照要宽，不然看不出差在哪）

选中元素 / 容器 `hidden` / 控件文案与 `class` /*回显值*/ / 计算字号 / 焦点 / 弹框文案。

### 5. 等页面稳定（否则被自己的初始化抢跑）

页面 `init()` 常连续跑两次加载，第二次开头会把「刚选中的东西」清掉 →
症状是**自相矛盾的状态组合**（选中=null 但控件显示已激活）。

```js
async function stabilize(){ let last=null;
  for(let i=0;i<60;i++){ const p=padEl();
    if(p && p===last && p.innerHTML.indexOf("标记")>=0){ await sleep(150); return true; }
    last=p; await sleep(150);} return false; }
```

### 6. 跑 + 抓

```python
subprocess.run([CHROME,"--headless=new","--disable-gpu","--no-sandbox",
  "--allow-file-access-from-files","--virtual-time-budget=20000",
  "--dump-dom","file://"+path], capture_output=True, text=True, timeout=180)
```

- **`--dump-dom` 对 `http://` 会返回空 DOM** → 必须走 `file://`。
- Shadow DOM 内容**不会**出现在 dump 里 → 结果要由页面脚本写进**主文档**的 `<div id="out">`。
- 探针页跑完即删，别留在被 serve 的目录里。

### 7. 必须带的三件套（否则就是自欺）

| 件 | 作用 | 例 |
|---|---|---|
| **差异控制** | 证明链路本身没坏，病只在某处 | 同类元素另一实现（`<p>` 版署名）当场是绿的 |
| **体检** | 证明环境是真环境 | 断言某已知元素计算字号 = 期望值（80px），不是兜底 16px |
| **负控制** | 证明会红 | 环境变量指向**修复前**的源码，同一回路应变红、退出码非 0 |

负控制基线做法：从当前文件**按补丁原文反推**出修复前版本，并核对**字节数与交付记录一致**（一致即反推无偏差）。

## 输出与退出码

每项 `✓/✗` + 明细行；末尾 `RESULT: GREEN（N 项全过）` / `RESULT: FAIL (X 红)`；`sys.exit(1)` 于失败。
这样非程序员也能验收：**一条命令、看末行**。

## 坑清单（都真撞过）

1. `--dump-dom` + `http://` → 空 DOM。走 `file://`。
2. 大 CSS 经 JS 字符串字面量内联 → **脚本整块不执行**（无报错）。用 `<style id>`。
3. 函数级断言全绿 ≠ 交互可用（选择器/DOM 可见性/CSS 计算值全在函数之外）。
4. 离线跑时不喂模板 CSS → 计算值退化 → 档位类断言假绿。
5. `init()` 二次加载抢跑 → 状态自相矛盾 → 先 `stabilize()`。
6. Chrome/系统 python 版本差异：写完用**用户 README 里那条命令**（如 `python3`）原样跑一遍。
7. **多处 harness 各自复制装配代码 → 必然漂移**：一个脚本内联了模板 CSS、另一个忘了 → 一份真一份假（实测：一个脚本的护栏用例「从没注入过目标风格 CSS」→ 假绿）。
   把装配抽成**共用模块**（本项目 `web/_harness_css.py`：`build(index_html, app_js_name="app.js") -> 完整 harness html`），所有验证脚本 + 一次性探针都 import 它。
   同一个坑撞第二次就抽件，别等第三次。
8. 一次性探针（只想查一个值时）**不要改正式验证脚本**：临时脚本 import 共用件 → 生成 `public/_probe_xxx.html` → 跑 → `rm` 掉。
   放 `public/` 是因为要相对引用 `app.js`；**忘了删就等于把探针页 serve 出去了**（跑完立刻 `ls public/` 复查只剩正式三件套）。
9. **只断言终态 → 假绿**：「改 A → 改 B → 断言 B」这种链，若 B 恰好等于初始态，则 **A 压根没生效也照样绿**。
   实测（阶段6.5）：⑦ 只抓「还原后 = t-meta」，但 t-meta 就是初始值 → 无法区分「改档位后还原」和「压根没改」。

10. **判据不埋对照值 → 恒绿**：拿「某一项等于某个值」当判据，若那一项全是同一个默认值，
    **什么都没发生也绿**。实测：拖放判据断言「gap 第 4 位 = 被拖块原值」，而所有 gap 默认都是 48
    ⇒ 没拖也绿。修：判据里**先改一个不重复的对照值**（如把原值埋成 7），只看它有没有跟到新位。

11. **断言口径抄错业务定义 → 恒假红**：判据不是照抄实现细节，是照业务定义推。
    实测：「段号不留空号」写成「段号 = 1..块数」，但同角色的块会归同一个段 ⇒ 段数本就少于块数 ⇒
    恒假红。正确口径是「去重后的最大段号 === 段数」。**假红和假绿一样有害**：它训练人忽略红灯。

12. **判据别写死「插到目标前 / 后」**：插前插后是实现的边角，改一次就假红。
    判该认的两件事实：**被操作的对象真的换了位置**、**其余对象的相对顺序一字不乱**。

13. **补交互判据常能挖出「功能从来没生效」级 bug**（它比功能 bug 更值钱，因为一直没人发现）。
    实测（CP3 补拖放判据）：① drop 处理里传的是**目标那一格**的对象 id 而非被拖那一格
    ⇒ 等价路径恒等 ⇒ 拖拽改序从来没生效过；② 回采函数会整体替换数组引用，
    调用方持有旧引用 ⇒ 刚排好的顺序静默丢失。
    ⇒ 判据打红时先分清**产品 bug / 判据 bug**，再动手 —— 本例两个都是产品 bug，但第 3 条下面的判据口径是判据 bug。
   → 每个**中间动作后都要抓一次快照**，让终态断言有对照物。
10. **派生 UI 态要在每个改状态的入口刷一次**：把「按钮可用性 / 徽标 / 计数」这类派生状态写成 `syncXxx(el)` 后，
    忘了在某个改状态的入口调它 → 症状是「**功能真的做了，但按钮还是灰的/文案没变，用户点不了**」。
    实测（阶段6.5）：`applyRole()` 改完档位只调了 `syncPad()`，没调 `syncRestoreBtn()` → 还原按钮停在灰色禁用态。
    这属于第 3 条的同类：**函数级验证看不见**（手动调 `restoreBlkRole()` 是通的）。
    排查口径：列出所有会改该状态的入口函数，逐个确认都调了 sync。
11. ⚠️ **硬报红：跟实测数字脱钩的断言** —— 性能探针页里写了 `if (n >= 12) add(false, "12 页塞满 ⇒ 应启用降级")`，
    于是 12 页实测首帧 23.5ms 也照红不误。**假红比假绿更坏**：假绿是没验到，假红是训练人忽略红灯
    （下次真出事也当噪音）。判据只认阈值（`首帧 < 800ms`），超不超标由数字说话；要配负控，就**人为压爆**
    （12 页 → 200 页，实测首帧 1180ms 报红），别靠页数硬编码触发。
12. **断言措辞要贴真源，别凭印象写近义词** —— 断言写「黄条含『不覆盖』」，产品文案是「**不静默覆盖**」⇒ 假红。
    断言里的关键词先 `grep` 真源文件核一遍再跑。
13. **跨页的「就绪条件」不能沿用** —— `open()` 若沿用 A 页的 ready_expr（如 `#saveState`），跳到没有该元素的 B 页会永远等不到 ⇒ 假红。
    每页给自己的就绪条件（如 `#run12` + `#out`）。

14. ⚠️ **本机 CDP/浏览器自动化必须先在脚本顶部清 proxy** —— WorkBuddy 环境会注入
    `http_proxy=http://<IP>:<端口>`（且 `no_proxy` 为空）。后果两连：
    ① python `urllib` 探 `<IP>:<CDP端口>/json/list` **走代理 ⇒ 502 Bad Gateway**；
    ② Chrome 子进程继承该变量 ⇒ 连不上本地页面。
    症状 ＝「等不到 CDP 端点」超时崩（实测 14 秒），**看着像代码 bug，其实是环境**。
    修法（脚本顶部，先于任何网络调用）：
    ```python
    for _k in ("http_proxy","HTTP_PROXY","https_proxy","HTTPS_PROXY","all_proxy","ALL_PROXY"):
        os.environ.pop(_k, None)
    os.environ["no_proxy"] = os.environ["NO_PROXY"] = "<IP>,localhost"
    ```
    实测（2026-09-28 CP6 冒烟）：不清 ⇒ 崩；清了 ⇒ 正常。**独立探针脚本同样要清**（别只清正式脚本）。
14. **关浏览器时服务线程喷 `BrokenPipe` 栈** —— 那是「关闭顺序」的噪音不是判据；整轮把 `sys.stderr` 指向 `os.devnull`，
    但**别吞真异常**（上下文管理器 `__exit__` 返回 False，判据自身的 traceback 照常放行）。
15. **性能类判据的落点是「该不该动手」，不是「功能做了没有」** —— 实测 12 页 23.5ms / 刷新 20.7ms 远未达阈值 ⇒
    结论是「**暂不上降级，维持现状**」，这也是一条有价值的绿。别为了凑「功能做了」硬造一个 ✗。
