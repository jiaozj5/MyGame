# v0.4 架空世界事件覆盖

## 资产边界

`content/world-events.json` 是版本 `0.4.0` 的单一宏观资产库：20 个领域，每域 6 项，共 120 项。背景是澄川诸邦与新历，事件不是现实历史重演，也没有按年份写定的发展结局。它们是已编写并经过规则检查的有限设计样本，仍需人工试玩与内容审阅，不能代表世界上所有人的全部可能经历。

宏观事件由世界规则抽取；玩家在社会响应事件中处理个人处境，不会通过一道选择题直接改变国家政策。事件的成本、收益、门槛与权重都是待平衡设计假设，不能当作经济预测或现实政策结论。事故可以造成纯损失；修复也需要条件、资源与时间，不保证发生。

- `requires` 中的条件同时成立才可进入候选池。只读 20 个既定指标、4 类互斥模式和明确来源的事实旗标。
- 指标范围为 0–100。事件只用 `metric`、`flag`、`mode` 三类世界动作，不直接修改玩家或 NPC。
- `once`、`cooldown` 控制重现；每次抽取仍重新检查前提。事件窗口和权重不等于发生承诺。
- `_alive` 记录设施能否使用，`_ever_built` 记录历史。建立、关闭、重建都必须有明确效果；回顾性经历和已获知识不会随设施关闭被自动抹去。
- 四种尺度是叙事观察范围，不是四套独立国家、人口或轨道物理模拟。当前没有完整空间地图、物资守恒、机构预算账本或通用生成资产平台。

## 20 领域覆盖矩阵

每行六个标题直接来自可执行资产，包含不同的发展路线、风险与适应；不要求每次人生遇到每个领域。

| 领域 ID / 名称 | 默认尺度 | 六项宏观主题 |
| --- | --- | --- |
| `economy` 经济与机会 | 国家与地区 | 沿线零件作坊形成协作圈；新项目的融资窗口放宽；扩张中的账目开始收缩；预算转向修旧而非新建；合作社建立就近交换网络；公开账本后的公共分担方案 |
| `labor` 劳动与就业 | 国家与地区 | 训练网络接上实际岗位；自动化先改变了重复岗位；协商缩短连续劳动时段；几条生产链出现拖欠；拖欠清单进入公开清偿；公共小屋里长出劳动合作社 |
| `housing` 住房与城市 | 国家与地区 | 合作租住把维修费摊开；城市边缘成片动工；新住区亮灯的窗户变少；受损住户迁入较安全地段；照护网络推动住处改造；土地使用改走共同协商 |
| `education` 教育与知识 | 国家与地区 | 学校与作坊接成训练网络；跨地区课堂共享研究资料；被保存的语言回到课堂；紧张局势压缩学术往来；临时教室追上迁入的人口；昂贵课程和普通课堂拉开距离 |
| `health` 公共卫生与照护 | 国家与地区 | 供水改善后基层照护扩展；拥挤地区出现公共健康警报；协作协议把照护送到缺口处；长期照护从家里延伸到社区；设备更新快于服务覆盖；区域共同采购缓解照护费用 |
| `population` 人口与迁移 | 国家与地区 | 新的口音来到车站；一批熟练工同时退休；带着旧门牌回来；照护站排出轮值表；边界上的新检查站；安置楼有了邻里议事桌 |
| `culture` 文化与共同生活 | 国家与地区 | 把不同的乡音录下来；旧礼堂重新亮灯；新区边缘的一排老屋；沿海路巡回的节庆；只剩一套演出目录；修回能继续生活的老街 |
| `information` 信息与传播 | 国家与地区 | 窗口旁多了一台查询机；地方采编站重新招人；查询屏停在同一页；转发比核实更快；把更正也送到街头；检索结果多了付费门 |
| `governance` 治理与公共能力 | 国家与地区 | 公共账本摆上桌面；几张调度表并成一张；各地开始各排各的队；把争议写进共同章程；两张单据上的同一批材料；不同窗口约定互相接件 |
| `rights` 权利与公民生活 | 国家与地区 | 申诉不再只剩一扇门；临时限制留在告示栏上；逐条撤下临时告示；被系统拒绝的人带来凭证；旧证件得到重新承认；查询目录学会少留一点信息 |
| `trade` 国际贸易与往来 | 邦际 | 货车开始使用共同通行单；港口接进更远的航线；装好的货停在边检外；绕远路的区域协议；区域航线暂停接单；跨邦凭证开始互认 |
| `conflict` 战争与和平 | 邦际 | 边境哨所多了一层灯；护航船在狭窄水道相撞；围着供能表达成的短暂停火；停火条款一条条签下；观察员走进停火地带；粮车在停火线上被扣下 |
| `energy` 能源转型 | 行星 | 屋顶电站接入共同电网；大电站接管高峰供能；储能站停机检查；封闭试验场第一次点亮；试验供能通过持续运行考验；试验场停止连续运行 |
| `food` 食物与农业 | 行星 | 试验田不再只种一种作物；产量跃上新的台阶；粮仓里的空位多了起来；把下一季的种子留住；较少的水也收回一季粮；合作粮仓改签长期收购单 |
| `infrastructure` 基础设施 | 国家与地区 | 分开的线路连成一张网；公共水管接到更远的街口；慢车驶过新的联络桥；泄洪闸旁建起值班屋；停电的主干线重新合闸；桥检报告让列车停下来 |
| `ecology` 生态与资源 | 行星 | 出口走廊下游出现浑水；上下游共担河岸修复；轮作试验留下更厚的土层；零散生境之间留出通道；新的矿区带来能源与伤口；维修与回收接上生产网络 |
| `climate` 气候与适应 | 行星 | 连续炎热季节拉长了用电高峰；几个流域同时进入缺水观察期；缺水地区重新商定取水顺序；遮阴和通风成为公共改造项目；轨道与地面观测接上地方预警；低排放供能开始替代旧设备 |
| `disaster` 自然灾害与修复 | 行星 | 洪水越过了几处旧防线；一次地震打断了区域联络；震后复建从检查清单重新开始；预警给洪水中的撤离多留了时间；退水之后重新校核防护标准；干热中的山火逼近居民点 |
| `technology` 技术与人工智能 | 前沿 | 开放实验网络建立可复查的成果库；平台把自动化服务推向更多行业；自动化分配被发现系统性漏掉一些人；通过复查的自动化服务有限重启；紧张局势使关键技术转向封闭维护；共同维护的工具重新打开技术接口 |
| `space` 太空与前沿 | 前沿 | 联合轨道观测站完成在轨调试；轨道服务因故障停止连续观测；替换组件通过复查，轨道观测恢复；地面封闭循环舱完成长期试验；小型域外研究驻点进入轮换运行；补给压力迫使研究驻点结束轮换 |

## 跨领域前事、分支与恢复

以下是已经写进 `requires` / `effects` 的因果链。箭头表示后项读取前项留下的条件，还需满足资产中的其他门槛，并非自动排进下一幕。

| 链 | 已实现的依赖与分支 |
| --- | --- |
| 手艺到产业 | `education.apprenticeship_network` → `labor.training_compacts` → `economy.parts_cluster`；产业还需 `trade.regional_corridor` 留下可用走廊。 |
| 公共空间到合作路线 | `culture.shared_spaces` → `labor.cooperative_route` → `housing.rent_compacts` / `economy.local_exchange` / `food.grain_coops` / `ecology.reuse_network`。 |
| 贸易到迁移再到教育 | `trade.regional_corridor` → `population.arrival_wave` → `education.traveling_classrooms`；进入新地区不等于知识入口已经充足。 |
| 记忆到课程 | `culture.language_archive` → `education.local_curriculum`，地方课程需要先有可使用的档案。 |
| 扩张的两种后果 | `economy.credit_expansion` → `housing.edge_expansion`；就业低迷时可出现 `housing.vacancy_hollowing`，也可引出 `culture.heritage_dispute` → 协商路线下的 `culture.community_restoration`。 |
| 公开记录到信息保护 | `governance.public_ledger` → `information.access_portal` → `rights.data_protection` → `trade.shared_standards`。 |
| 审计争议到治理分岔 | `governance.procurement_scandal` 写入 `audit_requested`；未解决争议加公共能力 ≤55、信任 ≤55 才可能进入 `governance.regional_fragmentation`。`governance.participatory_compact` 或 `governance.service_accord` 核对争议后清除旗标并转回协商治理。 |
| 自动化事故与再次复核 | `technology.platform_rollout` → `technology.algorithm_incident` → `rights.algorithm_appeals` → `technology.audited_restart`。每次事故会重置审查旗标，申诉事件允许在冷却后再次发生，第二次事故仍有恢复入口。 |
| 研究到能源试验再到前沿 | `education.open_science` → `technology.open_research` → `energy.advanced_trial`；`energy.trial_success` 与 `energy.trial_failure` 读取同一试验状态，任一结束会关闭试验进行中旗标。只有成功验证且设施仍在运行，才可能支持 `space.closed_loop_trial` 和域外驻点。 |
| 供水与照护 | `infrastructure.water_network` → `health.clinic_network`；另一路 `health.longterm_care` → `population.care_sharing` → `housing.accessible_stock`。公共设施与照护组织承担不同前提。 |
| 疫情与协作 | `health.infection_wave` 建立警报；已有 `governance.service_accord` 才可触发 `health.mobile_care`。流动照护结束当前警报，但不把健康直接恢复为满值。 |
| 轮作到低耗水农业 | `food.crop_diversification` 与劳动合作网络支持 `ecology.soil_recovery`；土壤恢复加仍在运行的 `food.seed_bank_network` 才能触发 `food.lowwater_trials`。 |
| 缺水的损失与适应 | `climate.drought_watch` → `food.drought_harvest` / `disaster.wildfire_season`；`climate.water_compact` 可结束当前缺水观察，但长期气候压力并未消失。 |
| 对峙、停火与返回 | `conflict.border_standoff` 可升级为 `conflict.shipping_incident` → `trade.port_disruption`，也可走向 `conflict.ceasefire_panel` → `rights.return_documents` → `population.return_resettlement`。缺粮且没有观察员的停火仍可能破裂。 |
| 灾后住处到定居 | `disaster.major_flood` / `disaster.tectonic_shock` / `disaster.wildfire_season` 写入 `housing_displaced` → `housing.safe_relocation`；新到居民同时具备安全住房时可出现 `population.settlement_compact`。一般道路复建不会替代个人住处安置。 |
| 电网、供能与震后恢复 | `infrastructure.shared_grid` → `energy.distributed_market`。`disaster.tectonic_shock` 关闭电网；仅在确实建过且现已停用时，`infrastructure.grid_repair` 才能恢复。储能站另有故障与重新验收入口。 |
| 产业扩张到流域修复 | `economy.parts_cluster` → `ecology.watershed_damage` → `ecology.river_restoration`，产值增长可能留下水质与健康代价。 |
| 轨道观测到地方响应 | `space.orbital_observatory` → `climate.shared_forecasts` → 洪灾中的 `disaster.warning_evacuation`。轨道故障会关闭观测与预警旗标；`space.orbital_service_rebuild` 只恢复观测，预警要重新校准。 |

## 设施和路线的反例边界

- 洪水会关闭防洪设施与种子库。`disaster.flood_recovery` 明确验收防护段，种子库仍需自己的建设／恢复事件；泛化的复建不会让所有设施自动复活。
- 轨道服务可能在地方预警建成前中断，因此故障正文只描述资料中断，不假定居民曾拥有联合预警服务。
- 域外驻点仍依赖地面补给。开工前能源保障至少 80，投入后至少 73，避免开工扣费就立刻满足 ≤68 的撤回条件；以后供能恶化仍可迫使撤回。
- 技术受限路线读取邦际紧张 ≥60，与贸易／紧急限制处于同一压力级别；没有固定年份解锁。先进供能成功与前沿驻点保留更高技术、公共能力、食物和能源前提。
- 铁路停运当前没有专用复通事件。停运事实会保留；通用基础设施改善不会把 `rail_link_alive` 擅自改回真。

## 后五领域的具体触发前提

下表列出生态、气候、灾害、技术与太空 30 项的完整规则前提，便于复查跨域入口。`flags` 未出现时按假读取；这里的“≠”表示当前模式不同。数值均是游戏量表。

| 事件 ID / 标题 | 同时满足的前提 |
| --- | --- |
| `ecology.watershed_damage` 出口走廊下游出现浑水 | `flags.export_cluster_ready` = 真；`metrics.ecology` ≤ 62；`flags.watershed_damage_active` = 假 |
| `ecology.river_restoration` 上下游共担河岸修复 | `flags.watershed_damage_active` = 真；`metrics.institutional_capacity` ≥ 42 |
| `ecology.soil_recovery` 轮作试验留下更厚的土层 | `flags.rotation_trials_ready` = 真；`flags.labor_coops_ready` = 真；`flags.soil_recovery_ready` = 假 |
| `ecology.habitat_corridors` 零散生境之间留出通道 | `metrics.ecology` ≤ 65；`metrics.social_trust` ≥ 48；`modes.governance` = negotiated |
| `ecology.extraction_frontier` 新的矿区带来能源与伤口 | `metrics.energy_security` ≤ 52；`metrics.ecology` ≥ 20 |
| `ecology.reuse_network` 维修与回收接上生产网络 | `flags.labor_coops_ready` = 真；`metrics.technology` ≥ 45；`metrics.infrastructure` ≥ 40 |
| `climate.hot_seasons` 连续炎热季节拉长了用电高峰 | `metrics.climate_stress` ≥ 32 |
| `climate.drought_watch` 几个流域同时进入缺水观察期 | `metrics.climate_stress` ≥ 50；`flags.drought_watch_active` = 假 |
| `climate.water_compact` 缺水地区重新商定取水顺序 | `flags.drought_watch_active` = 真；`metrics.institutional_capacity` ≥ 40 |
| `climate.passive_cooling` 遮阴和通风成为公共改造项目 | `metrics.climate_stress` ≥ 45；`metrics.public_services` ≥ 40 |
| `climate.shared_forecasts` 轨道与地面观测接上地方预警 | `flags.orbital_station_alive` = 真；`metrics.institutional_capacity` ≥ 45；`flags.shared_alerts_ready` = 假 |
| `climate.lower_emissions` 低排放供能开始替代旧设备 | `modes.energy` = distributed；`metrics.energy_security` ≥ 60；`metrics.technology` ≥ 55 |
| `disaster.major_flood` 洪水越过了几处旧防线 | `metrics.climate_stress` ≥ 48；`flags.flood_disruption_active` = 假 |
| `disaster.tectonic_shock` 一次地震打断了区域联络 | `flags.quake_disruption_active` = 假 |
| `disaster.reconstruction_audit` 震后复建从检查清单重新开始 | `flags.quake_disruption_active` = 真；`metrics.institutional_capacity` ≥ 38 |
| `disaster.warning_evacuation` 预警给洪水中的撤离多留了时间 | `flags.flood_disruption_active` = 真；`flags.shared_alerts_ready` = 真；`flags.orbital_station_alive` = 真 |
| `disaster.flood_recovery` 退水之后重新校核防护标准 | `flags.flood_disruption_active` = 真；`metrics.institutional_capacity` ≥ 40 |
| `disaster.wildfire_season` 干热中的山火逼近居民点 | `flags.drought_watch_active` = 真；`metrics.climate_stress` ≥ 55；`metrics.ecology` ≥ 15 |
| `technology.open_research` 开放实验网络建立可复查的成果库 | `flags.research_network_ready` = 真；`metrics.technology` ≥ 45；`metrics.energy_security` ≥ 45；`modes.technology` ≠ restricted；`flags.open_research_ready` = 假 |
| `technology.platform_rollout` 平台把自动化服务推向更多行业 | `metrics.technology` ≥ 52；`metrics.energy_security` ≥ 50；`flags.automation_services_alive` = 假；`flags.algorithm_incident_active` = 假；`modes.technology` ≠ restricted |
| `technology.algorithm_incident` 自动化分配被发现系统性漏掉一些人 | `flags.automation_services_alive` = 真；`flags.algorithm_incident_active` = 假 |
| `technology.audited_restart` 通过复查的自动化服务有限重启 | `flags.algorithm_incident_active` = 真；`flags.algorithm_audit_ready` = 真 |
| `technology.restricted_stack` 紧张局势使关键技术转向封闭维护 | `metrics.international_tension` ≥ 60；`metrics.technology` ≥ 45；`modes.technology` ≠ restricted |
| `technology.shared_tools` 共同维护的工具重新打开技术接口 | `flags.research_network_ready` = 真；`metrics.international_tension` ≤ 50；`metrics.knowledge_access` ≥ 50；`modes.technology` ≠ open |
| `space.orbital_observatory` 联合轨道观测站完成在轨调试 | `flags.open_research_ready` = 真；`metrics.technology` ≥ 65；`metrics.energy_security` ≥ 55；`metrics.infrastructure` ≥ 50；`flags.orbital_station_ever_built` = 假 |
| `space.orbital_service_failure` 轨道服务因故障停止连续观测 | `flags.orbital_station_alive` = 真 |
| `space.orbital_service_rebuild` 替换组件通过复查，轨道观测恢复 | `flags.orbital_station_ever_built` = 真；`flags.orbital_station_alive` = 假；`metrics.technology` ≥ 60；`metrics.energy_security` ≥ 50；`metrics.institutional_capacity` ≥ 40 |
| `space.closed_loop_trial` 地面封闭循环舱完成长期试验 | `flags.orbital_station_alive` = 真；`flags.advanced_energy_verified` = 真；`flags.advanced_energy_site_alive` = 真；`metrics.technology` ≥ 75；`metrics.food_security` ≥ 65；`flags.closed_loop_tested` = 假 |
| `space.research_outpost` 小型域外研究驻点进入轮换运行 | `flags.closed_loop_tested` = 真；`flags.orbital_station_alive` = 真；`flags.advanced_energy_verified` = 真；`flags.advanced_energy_site_alive` = 真；`metrics.technology` ≥ 82；`metrics.energy_security` ≥ 80；`metrics.food_security` ≥ 70；`metrics.prosperity` ≥ 65；`metrics.international_tension` ≤ 40；`flags.research_outpost_alive` = 假 |
| `space.outpost_withdrawal` 补给压力迫使研究驻点结束轮换 | `flags.research_outpost_alive` = 真；`metrics.energy_security` ≤ 68 |

## 验证与可证明的范围

已完成 JSON 解析、领域计数、完整 `validate_catalog` 校验：20 域各 6 项、事件 ID 唯一、操作与指标／模式合法，所有被读取的旗标均有写入来源，所有要求为真的旗标均有写真的来源。

内容侧另外构造满足各自前提的局部世界，检查 120 项均可应用、结果指标仍在范围内、模式合法；对 94 个必需真旗标分别移除，后续事件都被阻止。这只是局部规则反例检查，不证明从初始世界必然走到每项，也不评估出现频率是否好玩。

真实初始世界的多种子推进、历史重放、存档接续与实际触发覆盖见 [批量世界报告](../reports/world-v0.4.md)。报告保留未触发清单和对应文件哈希；内容改动后应重跑，不能把某一次抽样当成全域可达证明。当前不以 100% 抽样命中为目标，也没有为了让每条未来路线都出现而降低前沿条件。
