# TrustMRR 持续商机数据维护

这是本机维护入口，不是定时器。父级已配置定时任务；本设施不会创建/修改routine，也不发送消息、发帖、购买或注册。

## 当前基线与路径
- 初始池12,590项：公开目录126页、12,551项，另39条公开档案/推荐来源。没有按收入/成本/网页属性删记录。
- 793份已读公开档案、25项既存官网正文证据保留；23项人工候选见watchlist.json，仅待验证假设，不代表成本已证实。
- `baseline/projects.json`：不可变初始基线；`latest/projects.json` / `projects.jsonl`：最近事实版本；`latest/trustmrr-latest.zip`：JSON、JSONL、250项Markdown分片、字段说明和来源证据。
- `snapshots/YYYY-MM-DD/`：版本快照；`latest/version.json`：事实版本SHA256。
- `state.json`：源缓存时点、同口径指标观察、最初观察时点、最近全量状态；不是收入账本。
- `changes/*.json`：逐次新增/可比变化；`daily/latest-24h.md` / `.json`：供9点汇总。
- `run-status.json`、`logs/runs.jsonl`、`logs/failures.jsonl`：运行状态、失败与阻断。
- `delivery-state.json`：已实际交付的数据事实版本，仅防重复附件，不会发送附件。

## 执行命令
```bash
cd /workspace/trustmrr-monitor
python3 monitor.py status
python3 monitor.py refresh --mode auto
python3 monitor.py digest --hours 24
python3 -m unittest discover -s tests -v
```
`init`只用于首次建立基线，已有基线会拒绝覆盖。`refresh --mode incremental`只读最新入驻页和小观察表；`--mode full`也遵守每日一次和最小间隔，不是绕过限流的强制开关。

确认确实把某版本附件交付后，才可记录：
```bash
python3 monitor.py mark-delivered --version <latest/version.json中的semantic_version_sha256> --note '实际交付说明'
```
初始12,590条原始包已由父级交付，因此已记录相同事实版本，不再自动重复发送。

## 更新策略
- 默认本地日期每日首次、距上次全量至少12小时，尝试完整正常公开分页；当天后续只读 `/recent` 与23个公开档案。初始全量已在今天完成，不再重复抓126页。
- 同一日失败也不高频重跑全量；保留错误及覆盖，后续周期仍可更小范围更新，下一日再尝试全量。显式full同样不能跳过保护。
- 单并发、请求启动至少间隔0.9秒。近期页最小2小时，档案最小24小时；尊重公开Markdown中的next-refresh时间。具备ETag/Last-Modified时条件请求，304复用正文。未过期的缓存不发HTTP请求。
- 403/机器人挑战停止本轮及后续网络操作，等待人工核实；429至少退避6小时并尊重更长秒数Retry-After。没有替换UA伪装、登录、内部接口、代理或验证码绕过。
- 正常5xx/网络错误最多一次3秒退避重试；空页/结构变化不覆盖缓存或事实。只有解析通过的200正文才进入缓存。
- 全量动态翻页可能重复/漏项；coverage记录标称数、成功页、失败页、去重数和数量差，不声称100%全站。旧项目不因本轮缺失被删除或判定倒闭。

## 变化口径与静默
- 目录展示、近期页展示、公开档案、JSON-LD分开比较；不跨精度生成增长。目录金额变动只记“展示变化”，不生成精确增长百分比。
- 只有可比已观察0→正值，才记first_observed_positive，并明确不是实际首单；缺失→正值、新项目初次即为正，不记0→正。
- MRR、30天收入、累计收入、GMV分列。Gumroad/easytools已知GMV冲突不冒充营收。近期页只写Revenue、未给周期时保留revenue_unspecified，不猜累计/30天。
- 新入池不是新上线；成立日期不是上线日期；滚动30天收入下降不是客户流失；收入不是利润。成本全部未知，不套旧六关预筛。
- `material_change_count=0`时不主动打扰；仍须看status是否failed/blocked，不能把失败当“没有变化”。目录展示变化可供早间汇总人工判断，不承诺小推广必赚钱。
- 版本hash只反映相关项目事实，不因请求时点/分页位置/单纯同步时点推进而变化；文件完整性另看快照内checksums。没有事实变化就不重新打包/移动latest。
- 9点汇总读取daily与最新status；附件是否重复用latest/version.json对比delivery-state.json，而不是只比较上一轮是否有变化。

## 安全、恢复与限制
- 进程flock互斥，锁竞争退出75且不发请求；数据/状态文件原子替换；整个快照完成和ZIP校验后才切latest。
- `.pending-commit.json`是本地崩溃恢复日志；下一次持锁命令会验证版本并幂等完成latest/state/changes提交。不要手工删它；异常版本需人工检查。
- blocked后先读失败日志/robots与站点正常访问限制，不要擅自清除阻断重试。没有无人值守保证，也没有绕防护逻辑。
- 原始证据与日期快照保留，不自动清理；长期运行需要看磁盘。大多数项目仍只有目录信息；不是逐个官网审计。
- source URL及采集时点保留。旧缓存时点以既存文件mtime近似并说明；原始ISO带UTC，面向用户转换北京时间（UTC+8）。
- 当前只建立底层维护；不更改旧300项目Page、sellerfee/erasetext或它们的机会日志。

## 长期主执行方
用户后续已同意建立独立GitHub Pages研究站。集成完成后GitHub仓库为代码/数据主源、每天一次采集主执行方；本机routine应检查同步与深核/汇总，不应再与GitHub重复高频全量采集。具体仓库和命令将在集成完成时补充。
