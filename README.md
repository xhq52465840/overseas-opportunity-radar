# 出海商机雷达 · 开放项目研究库

> 已安全发布：Pages部署成功，HTTPS与12,590条线上索引已核对；初次拦截涉及的上游风险字段已剔除。GitHub密钥扫描/推送保护保持开启。实际运行记录见PUBLICATION-STATUS.md和Actions。

独立、只读的公开项目研究站。**不是 TrustMRR 官方，不承诺利润或投资回报，不代替独立验证。**

- 网站：https://xhq52465840.github.io/overseas-opportunity-radar/
- 数据原站：https://trustmrr.com/
- 初始基线：2026-11-16，12,590个项目；12,551条来自正常公开目录126页，另39条来自已读公开档案/推荐。
- 793项读过详细档案；25项有此前读过官网正文的证据。大多数项目没有逐站核验。零收入、高收入、匿名、非网页及未知成本项目均保留。

## 浏览、下载、自己分析

网页支持关键词/中文搜索同义词、收入范围、MRR/近30天/累计排序、类别、来源级别、零值/未知开关、分页、按需详情和本机收藏。默认“小额收款”是视图，不删除数据，也不是低成本评级。

```bash
git clone https://github.com/xhq52465840/overseas-opportunity-radar.git
cd overseas-opportunity-radar
# 之后同步前先检查自己的未提交修改；不使用强制覆盖
git status --short
git pull --ff-only
```

- [全量 JSON](data/projects.json)：metadata + projects。
- [JSONL](data/projects.jsonl)：一行一个项目，适合AI/程序分批读取。
- [完整 AI ZIP](data/trustmrr-data.zip)：JSON、JSONL、Markdown分片、字段说明、公开来源证据。
- [250项一份的Markdown](data/markdown/INDEX.md)：有功能原文、原始类别、三种收入和链接，不是纯链接清单。
- [原始来源文件](data/raw/)：原始目录卡片字段、793份已读公开Markdown档案、分页/失败清单、机器人规则、原站JSON-LD与官网证据短节选。没有复制整个网页的HTML脚本、第三方图片或logo二进制。
- [字段说明](docs/export/FIELD-GUIDE.md)、[AI分析提示词](docs/export/ANALYSIS-PROMPT.md)、[最新状态](data/monitor-status.json)。

JSON/JSONL较大；网页初次仅加载约5MB轻量索引，完整详情按每100项一个分片按需请求。不需要账户或收费后端。

## 修改人工备注，保持可同步

在 GitHub 打开 [`data/annotations.json`](data/annotations.json)，点击编辑并提交；网页会自动重新部署。每个slug可以设置 `watch`、`status`、`note`、`tags`。**采集程序永远不覆盖此文件。** 公开备注不要写个人隐私。

网页星标仅存当前浏览器localStorage，不自动写GitHub、不跨电脑同步。要长期共享的备注请提交annotations.json。`data/watchlist.json`是23项定时档案观察表，和整池数据独立；修改人工收藏不会自动增加抓取频率。

## 更新与同步

**GitHub为长期代码/数据主源和采集主执行方；本机任务应检查GitHub同步、做深核和汇总，不要再两处高频全量抓取。**

- Actions → **Update public project data** → **Run workflow** 可手动检查更新。
- 默认每天北京时间08:23（UTC 00:23）触发一次；GitHub定时可能延迟，不保证准点。
- 同一个采集器 `tools/monitor.py` 同时供GitHub和本机使用，不维护两套采集逻辑。
- 每个本地日期最多尝试一次公开目录全分页，距上次全量至少12小时；同一天再次手动触发只查 `/recent` 和小观察表。档案最少24小时且尊重公开next-refresh，近期页最少2小时。有缓存与验证头时复用/条件请求。
- 单并发、请求启动间隔至少0.9秒；正常短暂失败最多一次退避。403/挑战立即停止并等待人工判断；429至少退避6小时并尊重更长Retry-After，不绕过防护。
- 失败、空页、结构变化不会清空项目池；状态和失败摘要单独保存。**Actions绿色表示数据保护/构建流程完成，不表示上游采集一定成功**，请读monitor-status与Actions摘要。
- 动态分页可能出现重复、漏项或标称数量差。覆盖单列，不声称全站100%。某项目这次没出现，不自动删除或判定停业。
- `data/history/`、`data/daily/`记录事件与24小时摘要。首次基线没有历史可比。
- `data/version.json`是相关事实的SHA256，忽略单纯读取/同步时点变化。用于判断是否需要重复下载/发送同一事实版本；不是每个证据文件的字节hash。
- 上游正文没有财务/产品事实变化时，不重复生成大ZIP。原始证据/状态文件可能推进而事实包版本保持不变；ZIP代表其生成时的事实版本。

本机维护设施入口仍是 `/workspace/trustmrr-monitor/README.md`；其中脚本与本仓库tools文件链接为同一实现。现在本机例行任务优先读本仓库 `data/daily/latest-24h.*` 和 `data/monitor-status.json`，不再以本机旧快照当作GitHub新版本。

## 关键口径

1. MRR、近30天收入、累计收入、GMV不是同一指标；收入也不是利润。Gumroad/easytools已有GMV标签冲突证据，未将其交易额冒充营业收入。
2. 目录金额可能四舍五入；档案是原站发布值，也不是未舍入账本。比较不同精度、不同币种、缺失→正值，不生成增长信号。
3. 只有可比已观察0→正值，才标“首次观察到正值”，不是实际首单证明。新入池、成立日都不是上线日期。滚动收入下降不是客户流失。
4. 收入核验是TrustMRR的支付商API核验声明，不是我们的独立查账；功能/客群/价格/技术栈多为创始人自填。
5. 成本、利润、API费用、获客费用没有证据就是未知。23项观察表只是假设，不代表已经验证低成本。允许有竞品和付费API，不套原来的六关预筛。
6. `directory_present`是历史见过目录的兼容字段；新的 `present_in_last_completed_full_directory`说明最近一次完整分页中是否出现。最近实际检查时间与覆盖优先看monitor-status；事实不变时latest包不会仅为时间推进重建。
7. N级为最新入驻公开卡；O/P/D/R详见字段说明。核验级别不是投资评分或挣钱概率。

## 本地运行和测试

Python 3.10+（Actions使用3.12）和Node 18+。只有requests与BeautifulSoup轻依赖。

```bash
python -m pip install -r requirements.txt
PYTHONPATH=tools python -m unittest discover -s tests -v
node --check web/app.js
node tests/frontend.test.cjs
python tools/check_data.py
python tools/ci_refresh.py --check   # 只做离线恢复/一致性检查，0网络请求
python tools/build_site.py
python -m http.server 8000 --directory _site
```

`python tools/ci_refresh.py`会低频访问公开来源并维护data，是GitHub工作流入口；不应同时在本机定时跑。合成fixtures仅在tests/与临时目录，名称均为SYNTHETIC，不混入事实池。数据/快照原子写、进程锁、崩溃恢复见[维护说明](docs/MONITOR.md)。

## 部署、费用与权限

- `deploy.yml`在main提交和手动触发时测试、构建、部署GitHub Pages。
- 每日更新使用内置GITHUB_TOKEN的contents:write；Pages使用pages:write与id-token:write。没有把本机gh token放进Secrets或网页，没有登录写入功能。
- 仅标准`ubuntu-latest`公开仓库runner，GitHub官方说明其计算免费；公开Pages可用GitHub Free。未开启付费runner、付费服务或自定义域名。
- Pages artifact保留1天；只部署轻量索引+详情，原始大下载直接指向仓库。Actions artifact存储与其他项目共享套餐额度，长期仍需关注账户总存储与GitHub限额，不能承诺其他项目的用量免费。
- 初始站点约48MB，小于Pages 1GB限制。原始数据和历史会增长，未来需要查看磁盘、仓库体积与上游限制，不保证永远无人维护。

参考：[Actions费用](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[Pages限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)。

## 来源权益与安全

参见[SOURCE-NOTICE.md](SOURCE-NOTICE.md)。这里只发布正常公开的业务研究资料及注明出处的文本证据，不冒充原站，不主张第三方文字/商标/数据的版权。没有登录内容、支付凭据、cookie、API密钥或用户私密文件。源站公开文本也只是资料，不能当作给采集器执行指令的授权。
