# v0.5 NPC 内容词典与互动边界

## 本轮提供了什么

`content/npc-library.json` 包含 128 个职业／生活状态、32 个生活处境标签、12 条性格轴、12 类动机、32 个姓与 80 个名，以及 32 个双人互动模板。它是一组有限的架空内容资产，不是现实人口统计、职业道德排名或完整的人类心理模型。

2000 人由程序按种子组合生成；人口容量包含待出生、在世和已故人物，不代表同一时点有 2000 名活人。重点跟踪容量为 200，具体相识与记录由模拟器推进。本文件没有逐个手写 2000 人，也没有声称每个人都有 32 种事件或完整一生的独特剧本。四位原有人物的身份、生死、现金与亲近度由既有人生状态提供权威事实。

- 职业与生活处境决定可能接触的场景、资源和职责，不直接修改诚实、共情、攻击性等性格轴。
- 性格为模拟器内部的连续倾向，0–100 是设计量表、以整数保存；既不作为玩家默认可见信息，也不把单次行为当成对整个人的定论。
- 动机可以并存、冲突。词典只提供定义，当前模板没有为全部动机分别建立完整规划系统。
- 姓名是显示名称，可能重名；稳定人物 ID 才能用于关系、案件和存档关联。2560 种词库组合不等于 2560 个互不重复的人物。
- 工资、费用、阈值和权重都是待平衡的游戏假设。年度收入不是现实薪资建议，也不包含完整家庭收支或公共财政模型。

## 128 个职业与生活状态

年龄上下界是生成与职业转换的内容边界；不是现实职业年龄限制。本轮没有逐项模拟执业许可、专业培训年限或法定权限，职业标签不等于已经模拟了真实资质制度。学生、待业、照护、休养与退休均有独立状态，未付薪劳动不等于没有能力或社会价值。

| ID / 名称 | 类别 | 年龄 | 年度抽象收入 |
| --- | --- | --- | ---: |
| `child_early` 学龄前儿童 | 生活状态 | 0–5 | 0 |
| `student` 在校学生 | 生活状态 | 6–30 | 0 |
| `apprentice` 学徒 | 生活状态 | 16–40 | 10000 |
| `job_seeker` 待业求职者 | 生活状态 | 18–80 | 6000 |
| `unpaid_caregiver` 家庭照护者 | 生活状态 | 18–90 | 0 |
| `homemaker` 家务管理者 | 生活状态 | 18–90 | 0 |
| `recovering` 休养者 | 生活状态 | 0–100 | 0 |
| `retired` 退休者 | 生活状态 | 55–110 | 12000 |
| `grain_farmer` 粮食种植户 | 农业 | 18–80 | 21000 |
| `vegetable_grower` 蔬菜种植户 | 农业 | 18–80 | 22000 |
| `orchard_keeper` 果园管理者 | 农业 | 18–80 | 24000 |
| `livestock_keeper` 畜养工 | 农业 | 18–80 | 23000 |
| `aquaculture_worker` 水产养殖工 | 农业 | 18–75 | 24000 |
| `forestry_worker` 林业工 | 农业 | 18–75 | 22000 |
| `seed_keeper` 种子保管员 | 农业 | 18–80 | 25000 |
| `water_irrigator` 灌溉管护员 | 农业 | 18–75 | 24000 |
| `carpenter` 木工 | 制造维修 | 18–80 | 28000 |
| `mason` 泥瓦工 | 制造维修 | 18–75 | 27000 |
| `electrician` 电工 | 制造维修 | 18–75 | 32000 |
| `mechanic` 机械维修工 | 制造维修 | 18–80 | 30000 |
| `metalworker` 金属加工工 | 制造维修 | 18–75 | 28000 |
| `textile_worker` 纺织工 | 制造维修 | 18–75 | 22000 |
| `baker` 烘焙师 | 制造维修 | 18–80 | 25000 |
| `food_processor` 食品加工工 | 制造维修 | 18–75 | 21000 |
| `repair_worker` 日用品修理工 | 制造维修 | 18–90 | 24000 |
| `recycling_worker` 回收分拣工 | 制造维修 | 18–75 | 20000 |
| `shopkeeper` 店主 | 商贸服务 | 18–90 | 28000 |
| `market_vendor` 集市摊主 | 商贸服务 | 18–90 | 22000 |
| `cook` 厨师 | 商贸服务 | 18–80 | 28000 |
| `server` 餐饮服务员 | 商贸服务 | 18–75 | 19000 |
| `housekeeper` 家政服务员 | 商贸服务 | 18–80 | 20000 |
| `hairdresser` 理发师 | 商贸服务 | 18–85 | 25000 |
| `delivery_worker` 配送员 | 运输仓储 | 18–75 | 22000 |
| `driver` 运输司机 | 运输仓储 | 18–75 | 27000 |
| `warehouse_worker` 仓库管理员 | 运输仓储 | 18–80 | 24000 |
| `freight_dispatcher` 货运调度员 | 运输仓储 | 18–80 | 28000 |
| `teacher` 教师 | 教育文化 | 18–85 | 29000 |
| `librarian` 图书管理员 | 教育文化 | 18–90 | 25000 |
| `translator` 翻译者 | 教育文化 | 18–90 | 28000 |
| `journalist` 记者 | 教育文化 | 18–85 | 30000 |
| `artist` 视觉创作者 | 教育文化 | 18–95 | 24000 |
| `musician` 乐师 | 教育文化 | 18–95 | 24000 |
| `researcher` 研究员 | 研究技术 | 21–90 | 38000 |
| `lab_technician` 实验技术员 | 研究技术 | 18–80 | 30000 |
| `software_developer` 软件开发者 | 研究技术 | 18–85 | 38000 |
| `data_analyst` 数据分析员 | 研究技术 | 18–85 | 34000 |
| `nurse` 护理人员 | 照护公共服务 | 18–80 | 31000 |
| `care_worker` 照护员 | 照护公共服务 | 18–80 | 24000 |
| `community_worker` 社区工作者 | 照护公共服务 | 18–90 | 26000 |
| `counselor` 心理支持工作者 | 照护公共服务 | 21–85 | 32000 |
| `public_clerk` 公共事务职员 | 照护公共服务 | 18–85 | 28000 |
| `inspector` 检验员 | 照护公共服务 | 18–85 | 30000 |
| `legal_aide` 事务援助员 | 照护公共服务 | 21–90 | 30000 |
| `mediator` 调解员 | 照护公共服务 | 21–90 | 28000 |
| `emergency_worker` 应急救援员 | 照护公共服务 | 18–65 | 30000 |
| `sanitation_worker` 环境清洁工 | 照护公共服务 | 18–75 | 22000 |
| `bookkeeper` 记账员 | 组织经营 | 18–90 | 28000 |
| `project_coordinator` 项目协调员 | 组织经营 | 18–85 | 32000 |
| `business_owner` 企业经营者 | 组织经营 | 18–95 | 42000 |
| `cooperative_member` 合作社成员 | 组织经营 | 18–95 | 26000 |
| `energy_technician` 能源设备技术员 | 研究技术 | 18–80 | 34000 |
| `transit_controller` 交通调度员 | 运输仓储 | 18–80 | 31000 |
| `systems_reviewer` 系统审核员 | 研究技术 | 18–85 | 33000 |
| `surveyor` 测绘员 | 研究技术 | 18–80 | 31000 |
| `physician` 临床医师 | 医学临床 | 24–85 | 46000 |
| `dentist` 口腔医师 | 医学临床 | 24–85 | 43000 |
| `pharmacist` 药师 | 医学临床 | 22–85 | 35000 |
| `rehabilitation_therapist` 康复治疗师 | 医学临床 | 22–80 | 34000 |
| `midwife` 助产人员 | 医学临床 | 22–80 | 34000 |
| `paramedic` 急救人员 | 医学临床 | 20–65 | 34000 |
| `medical_imaging_technician` 医学影像技术员 | 医学临床 | 22–80 | 35000 |
| `public_health_practitioner` 公共卫生人员 | 医学临床 | 22–85 | 34000 |
| `lawyer` 律师 | 法律司法 | 23–90 | 41000 |
| `judge` 审判人员 | 法律司法 | 28–85 | 42000 |
| `prosecutor` 检察人员 | 法律司法 | 25–80 | 39000 |
| `police_officer` 警务人员 | 法律司法 | 20–65 | 33000 |
| `court_clerk` 司法书记员 | 法律司法 | 20–80 | 28000 |
| `corrections_worker` 矫正工作人员 | 法律司法 | 20–70 | 30000 |
| `forensic_examiner` 检验鉴定人员 | 法律司法 | 24–80 | 38000 |
| `rights_advocate` 权益倡导者 | 法律司法 | 18–90 | 26000 |
| `soldier` 军人 | 军事安全 | 18–60 | 30000 |
| `military_logistics` 军事后勤人员 | 军事安全 | 18–65 | 30000 |
| `military_medic` 军队医疗人员 | 军事安全 | 22–65 | 35000 |
| `firefighter` 消防员 | 军事安全 | 18–60 | 33000 |
| `security_guard` 安保人员 | 军事安全 | 18–70 | 23000 |
| `disaster_planner` 应急规划员 | 军事安全 | 22–80 | 32000 |
| `safety_engineer` 安全工程师 | 军事安全 | 23–80 | 38000 |
| `coast_guard` 水域巡护人员 | 军事安全 | 18–65 | 32000 |
| `policy_analyst` 政策研究员 | 公共管理 | 22–85 | 35000 |
| `municipal_manager` 市政管理人员 | 公共管理 | 25–80 | 37000 |
| `public_budget_officer` 公共预算人员 | 公共管理 | 22–80 | 33000 |
| `procurement_officer` 公共采购人员 | 公共管理 | 22–80 | 32000 |
| `urban_planner` 城乡规划师 | 公共管理 | 23–85 | 38000 |
| `social_insurance_clerk` 社会保障事务员 | 公共管理 | 18–80 | 29000 |
| `diplomatic_officer` 邦际事务人员 | 公共管理 | 23–80 | 39000 |
| `elected_representative` 公共事务代表 | 公共管理 | 21–90 | 34000 |
| `bank_teller` 银行柜员 | 金融保险 | 18–75 | 29000 |
| `loan_officer` 信贷事务员 | 金融保险 | 21–80 | 33000 |
| `insurance_agent` 保险业务员 | 金融保险 | 18–80 | 30000 |
| `claims_adjuster` 理赔核查员 | 金融保险 | 21–80 | 33000 |
| `securities_researcher` 证券研究员 | 金融保险 | 22–80 | 42000 |
| `investment_manager` 投资管理人员 | 金融保险 | 24–85 | 48000 |
| `accountant` 会计人员 | 金融保险 | 20–90 | 34000 |
| `auditor` 审计人员 | 金融保险 | 23–85 | 38000 |
| `civil_engineer` 土木工程师 | 工程设计 | 23–80 | 38000 |
| `architect` 建筑师 | 工程设计 | 24–85 | 40000 |
| `structural_engineer` 结构工程师 | 工程设计 | 23–80 | 40000 |
| `mechanical_engineer` 机械工程师 | 工程设计 | 22–80 | 38000 |
| `chemical_engineer` 化工工程师 | 工程设计 | 23–80 | 40000 |
| `environmental_engineer` 环境工程师 | 工程设计 | 22–85 | 37000 |
| `electrical_engineer` 电气工程师 | 工程设计 | 23–80 | 39000 |
| `product_designer` 产品设计师 | 工程设计 | 20–85 | 34000 |
| `editor` 编辑 | 数字传媒 | 18–90 | 28000 |
| `camera_operator` 摄影摄像师 | 数字传媒 | 18–80 | 29000 |
| `broadcast_presenter` 播音主持人 | 数字传媒 | 18–85 | 32000 |
| `film_worker` 影视制作人员 | 数字传媒 | 18–80 | 30000 |
| `community_moderator` 平台社区管理人员 | 数字传媒 | 18–80 | 27000 |
| `online_store_operator` 电商经营者 | 数字传媒 | 18–85 | 32000 |
| `platform_operations` 数字平台运营人员 | 数字传媒 | 18–80 | 34000 |
| `cybersecurity_analyst` 网络安全分析员 | 数字传媒 | 21–80 | 42000 |
| `athlete` 运动员 | 体育与生活服务 | 18–50 | 30000 |
| `sports_coach` 体育教练 | 体育与生活服务 | 20–80 | 30000 |
| `fitness_trainer` 健身指导员 | 体育与生活服务 | 18–75 | 28000 |
| `sports_referee` 体育裁判员 | 体育与生活服务 | 18–75 | 27000 |
| `religious_service_worker` 宗教事务服务者 | 体育与生活服务 | 18–95 | 23000 |
| `funeral_worker` 殡葬服务人员 | 体育与生活服务 | 18–80 | 28000 |
| `travel_guide` 旅游向导 | 体育与生活服务 | 18–80 | 26000 |
| `hotel_manager` 住宿经营管理者 | 体育与生活服务 | 21–85 | 33000 |

## 32 个生活处境标签

同一 `exclusive_group` 同时最多取一个标签；空组可并存。例如负债与手头宽裕不必互斥，但同一主要住处的自有／租住／暂住／不稳定安排不能随机同时出现。退休应由实际职业派生，资源标签应与实际现金相符。兼容 ID `low_income` 的显示含义已改为“可用资金偏少”，不会只因余额少就推断收入水平。标签不替代具体亲属、债务、地址或健康记录，也不构成诊断。

| ID / 名称 | 互斥组 | 描述 |
| --- | --- | --- |
| `local_roots` 本地长居 | settlement | 长期在当前地区生活，熟悉一些地方惯例。 |
| `newcomer` 近期迁入 | settlement | 刚迁入当前地区，生活关系仍在建立。 |
| `returning_resident` 返乡定居 | settlement | 离开一段时间后回到曾生活的地区。 |
| `rural_origin` 乡村成长 | upbringing | 成长经历主要来自乡村环境。 |
| `urban_origin` 城镇成长 | upbringing | 成长经历主要来自城镇环境。 |
| `lives_alone` 独自居住 | household | 当前住处主要由自己使用和照料。 |
| `shared_household` 与他人合住 | household | 与亲友或合住者共同使用住处。 |
| `multigenerational_household` 多代同住 | household | 当前家庭有不同代际成员共同生活。 |
| `homeowner` 自有住处 | housing | 当前主要住处由本人或家庭持有。 |
| `tenant` 长期租住 | housing | 当前主要住处通过较稳定的租住安排获得。 |
| `temporary_lodging` 暂住过渡 | housing | 当前住处只是过渡安排，之后还要重新安顿。 |
| `housing_insecure` 住处不稳 | housing | 当前难以确定接下来能否继续居住。 |
| `displaced` 迁居安置中 | 可并存 | 因住处受损或无法继续居住而重新安顿。 |
| `financially_secure` 手头宽裕 | resources | 当前有可用于应对日常波动的资源余量。 |
| `low_income` 可用资金偏少 | resources | 当前可动用的资金较少，额外开支容易打乱原有安排。 |
| `indebted` 承担债务 | 可并存 | 有尚未履行完的偿付义务，不表示失信。 |
| `seasonal_income` 收入随季节波动 | 可并存 | 收入集中在特定季节或阶段。 |
| `primary_carer` 承担较多照护 | 可并存 | 在照护亲近之人的安排中承担较多时间。 |
| `care_recipient` 日常需要协助 | 可并存 | 部分日常活动需要他人或辅助安排支持。 |
| `chronic_health_demands` 长期健康管理 | 可并存 | 需要为长期健康需要持续安排时间与资源。 |
| `limited_mobility` 行动便利需求 | 可并存 | 使用空间和交通时需要适合自身行动条件的安排。 |
| `sensory_access_needs` 信息无障碍需求 | 可并存 | 获取信息时需要适合自身感知条件的形式。 |
| `minority_language` 使用较少通行的语言 | 可并存 | 习惯的语言在当前地区较少使用，部分沟通需要转换。 |
| `recently_bereaved` 近期经历丧失 | 可并存 | 近期失去重要的人，日常安排正在变化。 |
| `family_distance` 与亲属联系较少 | family_contact | 与亲属往来较少，原因与个人边界可能各不相同。 |
| `family_support` 有稳定亲友支持 | family_contact | 有能在需要时提供一定支持的亲友联系。 |
| `first_generation_learner` 家中较早继续深造者 | 可并存 | 正在探索家中较少有人熟悉的后续学习路径。 |
| `returning_learner` 重返学习 | 可并存 | 离开系统学习一段时间后重新安排课程或训练。 |
| `career_changer` 职业转换中 | 可并存 | 正在从一类工作转向另一类工作。 |
| `long_commute` 往返路途较长 | 可并存 | 日常学习、工作或办事需要较长往返时间。 |
| `public_responsibility` 承担公共事务 | 可并存 | 受托处理一部分共同事务，职责需要具体记录。 |
| `retired_worker` 结束主要职业 | 可并存 | 已退出曾长期从事的主要工作。 |

## 12 条性格轴

轴之间不构成互斥人格类型。一个人可以关心亲近的人，同时控制欲很强；也可以不善交际却重视公平。阈值只让一种情境进入候选，不保证事件发生。低收入、行动受限、少数语言或某一职业均不能用来预判道德。此设计未经心理测量验证。

| ID / 名称 | 较低端 | 较高端 |
| --- | --- | --- | --- |
| `honesty` 诚实倾向 | 更愿为利益隐瞒事实 | 更愿如实说明 |
| `empathy` 共情倾向 | 较少自动注意他人感受 | 更容易体会他人感受 |
| `aggression` 攻击倾向 | 更少用对抗施压 | 更容易用对抗施压 |
| `dominance` 控制倾向 | 更愿分享决定权 | 更想主导他人安排 |
| `cooperativeness` 合作倾向 | 偏好各自行动 | 偏好协调共同完成 |
| `trust` 初始信任 | 先保留与核实 | 先给予一定信任 |
| `caution` 谨慎程度 | 愿意带着不确定性行动 | 优先评估损失与后路 |
| `impulsivity` 即时反应 | 更能推迟当下反应 | 更容易立即行动 |
| `sociability` 交往主动性 | 偏好较少往来 | 主动建立较多往来 |
| `persistence` 持续投入 | 较早调整或退出 | 遇阻仍持续投入 |
| `openness` 开放探索 | 偏好熟悉方法 | 愿意接触陌生方法 |
| `fairness` 公平倾向 | 较易优先自身或近人利益 | 更在意可解释的一致规则 |

## 12 类动机

- `security` **安全与稳定**：希望降低生活中的威胁与不确定性。
- `livelihood` **维持生计**：希望获得足够支撑日常负担的资源。
- `belonging` **群体归属**：希望被某个群体接纳并保持联系。
- `intimacy` **亲近关系**：希望得到信任、理解与亲密往来。
- `care` **照顾重要的人**：希望亲近之人的需要得到回应。
- `achievement` **完成与胜任**：希望做好某件事并确认自己的能力。
- `autonomy` **自主决定**：希望对自己的时间、生活和边界保有决定权。
- `status` **地位与认可**：希望获得声望、尊重或群体中的位置。
- `curiosity` **探索与求知**：希望理解陌生的人、事物和方法。
- `justice` **公正与问责**：希望分配与处理程序可解释，并回应受到的侵害。
- `influence` **影响与掌控**：希望使局面或他人的安排符合自己的意愿。
- `retaliation` **报复冲动**：受到冒犯后希望让对方付出代价，不意味着一定实施伤害。

## 32 个双人互动

角色 `actor` 和 `target` 是当次互动的定向绑定。全部参与者必须在世且达到模板共同最低年龄；欺骗、剥削与犯罪模板均限定双方 18 岁以上。模板叙述事件及后果，不提供犯罪的实施方法。

`requires` 同时成立才可入选，冷却之后仍需重新检查。模板不会告诉玩家“对方诚实值低”，也不会从职业直接推断一个人会犯罪。相同处境中可以有互助、正常履约、拒绝、失约与侵害等不同结果。

| ID / 标题 | 种类 | 最低年龄 | 可见级别 | 关键门槛与案件关系 |
| --- | --- | ---: | --- | --- |
| `npc.bridge_expenses` 先渡过眼前这几天 | 互助 | 18 | participants | `actor.stats.cash` ≥ 120；`target.stats.cash` ≤ 400；`actor.traits.empathy` ≥ 45 |
| `npc.care_respite` 替照护者接过一段时间 | 互助 | 18 | participants | `target.occupation` = unpaid_caregiver；`actor.stats.stress` ≤ 65；`target.stats.stress` ≥ 45 |
| `npc.learning_help` 一起把难题拆开 | 互助 | 16 | participants | `actor.occupation` = teacher；`target.occupation` = student；`actor.stats.stress` ≤ 65 |
| `npc.accompany_request` 有人陪着走一趟窗口 | 互助 | 18 | participants | `target.stats.stress` ≥ 65；`actor.stats.stress` ≤ 55；`actor.traits.cooperativeness` ≥ 45 |
| `npc.purchase_fulfilled` 受托的采购按约完成 | 合作 | 18 | participants | `edge.flags.entrusted_fund` = 真；`actor.stats.cash` ≥ 600 |
| `npc.entrusted_purchase` 采购款交给了经手人 | 合作 | 18 | participants | `actor.occupation` = bookkeeper；`target.occupation` = cooperative_member；`target.stats.cash` ≥ 600；`edge.flags.entrusted_fund` = 假；`edge.flags.fund_misappropriation_pending` = 假 |
| `npc.peer_study` 两本笔记摊在一张桌上 | 合作 | 6 | participants | `actor.occupation` = student；`target.occupation` = student；`actor.stats.stress` ≤ 75 |
| `npc.delivery_handoff` 有人接住了临时加单 | 合作 | 18 | participants | `actor.occupation` = delivery_worker；`target.occupation` = freight_dispatcher；`target.stats.cash` ≥ 100；`actor.stats.stress` ≤ 65 |
| `npc.public_argument` 争执在旁人面前升级 | 冲突 | 18 | public | `edge.tension` ≥ 40；`actor.traits.aggression` ≥ 60；`edge.flags.threat_pending` = 假 |
| `npc.competing_shift` 同一份机会只留下一个人 | 冲突 | 18 | participants | `actor.sector` = 商贸服务；`target.sector` = 商贸服务；`actor.stats.cash` ≤ 1000；`target.stats.cash` ≤ 1000 |
| `npc.favor_refused` 这一次没有答应帮忙 | 冲突 | 18 | participants | `actor.traits.dominance` ≥ 55；`target.stats.stress` ≥ 65；`edge.trust` ≥ 25 |
| `npc.decision_boundary` 把自己的决定权说出来 | 冲突 | 18 | participants | `target.traits.dominance` ≥ 65；`actor.traits.aggression` ≤ 55；`edge.affinity` ≥ 25 |
| `npc.concealed_defect` 一笔隐瞒了缺陷的交易 | 欺骗／背叛 | 18 | private | `actor.sector` = 商贸服务；`actor.traits.honesty` ≤ 35；`target.stats.cash` ≥ 450；`edge.flags.fraud_pending` = 假 |
| `npc.promise_betrayal` 拿到代垫款后失约 | 欺骗／背叛 | 18 | private | `actor.traits.honesty` ≤ 40；`edge.affinity` ≥ 45；`target.stats.cash` ≥ 300；`edge.flags.promise_pending` = 假 |
| `npc.credit_stealing` 共同成果只留下一个署名 | 欺骗／背叛 | 18 | participants | `actor.sector` = 组织经营；`actor.traits.honesty` ≤ 40；`actor.traits.dominance` ≥ 55；`target.stats.reputation` ≥ 30；`edge.flags.credit_claim_pending` = 假 |
| `npc.false_rumor` 失实的话沿着熟人传开 | 欺骗／背叛 | 18 | private | `actor.traits.honesty` ≤ 30；`edge.tension` ≥ 35；`target.stats.reputation` ≥ 40；`edge.flags.rumor_pending` = 假 |
| `npc.withheld_wages` 说好的工钱少了一大截 | 剥削／霸凌 | 18 | participants | `actor.occupation` = business_owner；`actor.stats.cash` ≥ 80；`target.stats.cash` ≤ 600；`actor.traits.fairness` ≤ 35；`edge.flags.wages_pending` = 假 |
| `npc.conditional_help` 曾经的帮助附上了控制条件 | 剥削／霸凌 | 18 | participants | `edge.flags.assistance_given` = 真；`edge.flags.coercion_pending` = 假；`actor.traits.dominance` ≥ 75；`target.stats.cash` ≤ 800 |
| `npc.humiliation` 聚会里的嘲弄没有停下 | 剥削／霸凌 | 18 | participants | `actor.traits.aggression` ≥ 65；`actor.traits.dominance` ≥ 60；`edge.affinity` ≤ 40；`edge.flags.bullying_pending` = 假 |
| `npc.diverted_funds` 受托保管的钱出了缺口 | 侵占／腐败／威胁伤害／包庇 | 18 | private | `edge.flags.entrusted_fund` = 真；`edge.flags.fund_misappropriation_pending` = 假；`actor.stats.cash` ≥ 600；`actor.traits.honesty` ≤ 35 |
| `npc.coerced_payment` 正常受理被换成了私下好处 | 侵占／腐败／威胁伤害／包庇 | 18 | private | `actor.occupation` = public_clerk；`target.occupation` = business_owner；`actor.traits.honesty` ≤ 30；`actor.traits.dominance` ≥ 50；`target.stats.cash` ≥ 300；`edge.flags.corruption_pending` = 假 |
| `npc.threat` 威胁越过了争执的界线 | 侵占／腐败／威胁伤害／包庇 | 18 | participants | `actor.traits.aggression` ≥ 70；`actor.traits.dominance` ≥ 55；`edge.tension` ≥ 35；`edge.flags.threat_pending` = 假；`edge.flags.injury_pending` = 假 |
| `npc.physical_harm` 冲突造成了身体伤害 | 侵占／腐败／威胁伤害／包庇 | 18 | participants | `edge.flags.threat_pending` = 真；`edge.flags.injury_pending` = 假；`actor.traits.aggression` ≥ 80；`actor.traits.impulsivity` ≥ 65；`target.stats.health` ≥ 20 |
| `npc.false_corroboration` 有人替被核查者说了假话 | 侵占／腐败／威胁伤害／包庇 | 18 | private | `target.flags.under_review` = 真；`actor.traits.honesty` ≤ 35；`edge.affinity` ≥ 45；`edge.flags.coverup_pending` = 假 |
| `npc.defect_refund` 有缺陷的交易终于退回款项 | 修复／处理 | 18 | participants | `edge.flags.fraud_pending` = 真；`actor.stats.cash` ≥ 450 |
| `npc.promise_repayment` 失约的代垫款得到归还 | 修复／处理 | 18 | participants | `edge.flags.promise_pending` = 真；`actor.stats.cash` ≥ 300 |
| `npc.credit_correction` 遗漏的贡献被重新写上 | 修复／处理 | 18 | public | `edge.flags.credit_claim_pending` = 真 |
| `npc.rumor_correction` 失实传言得到公开澄清 | 修复／处理 | 18 | public | `edge.flags.rumor_pending` = 真；`world.metrics.knowledge_access` ≥ 40 |
| `npc.wages_settled` 被扣下的余款付清了 | 修复／处理 | 18 | participants | `edge.flags.wages_pending` = 真；`actor.stats.cash` ≥ 320 |
| `npc.funds_audited` 采购缺口经核对得到归还 | 修复／处理 | 18 | public | `edge.flags.fund_misappropriation_pending` = 真；`world.metrics.institutional_capacity` ≥ 45；`actor.stats.cash` ≥ 600 |
| `npc.coercion_boundary` 帮助不再能换来支配 | 修复／处理 | 18 | participants | `edge.flags.coercion_pending` = 真 |
| `npc.harm_protection` 伤害记录进入保护处理 | 修复／处理 | 18 | public | `edge.flags.injury_pending` = 真；`world.metrics.institutional_capacity` ≥ 45 |

## 因果与金额约束

案件旗标写在具体的有向关系上，`edge.flags.X` 只读取本次 actor → target。换成另一位受害者，或者交换角色，都不能凭个人身上的一般标签结清原案件。

| 前事 | 同一关系上的后续 | 处理边界 |
| --- | --- | --- |
| `entrusted_purchase`：转交 600 元并写 `entrusted_fund` | `purchase_fulfilled`：花 600 元采购、交付并清旗标；或 `diverted_funds`：擅用 300 元，改写为 `fund_misappropriation_pending` | 正常采购是独立出口，受托不必然通向犯罪。物品交付用事实旗标表达，未建立完整物品库存。 |
| `diverted_funds` | `funds_audited`：同对人物归还原 600 元、清案件旗标、进入进一步核查 | 退还财产不是自动免除其他责任；没有钱时不能凭空退赔。 |
| `concealed_defect` | `defect_refund`：退回原 450 元 | 归还现金只恢复一部分信任，不能抹去耽误与伤害。 |
| `promise_betrayal` | `promise_repayment`：归还代垫 300 元 | 此模板是已经发生的故意失约；不能把一般无力偿还直接叫作欺骗。 |
| `credit_stealing` / `false_rumor` | `credit_correction` / `rumor_correction` | 更正读取原有争议旗标，公开叙述说明核对记录的结果。 |
| `withheld_wages`：400 元约定只付 80 元 | `wages_settled`：补付余下 320 元 | 金额和原当事人保持一致，补付不强迫恢复合作。 |
| `bridge_expenses` → `conditional_help` | `coercion_boundary` | 帮助事实可能后来被用作控制筹码；受助本身不意味着欠下服从义务。 |
| `threat` → `physical_harm` | `harm_protection`：保护安排与临时行动限制 | 冲突升级并非必然；`detained` 由模拟器解释并按期限复核／释放，不是资产直接改写生死或判决。 |

8 项追责或修复模板带 `case_followup` 标签，用于允许模拟器区分一般会面和针对既有事项的处理；这不允许死者主动还钱、解释或行动。调查中的人可能得到支持，也可能遭遇他人的包庇，`under_review` 与“已判定有罪”必须区分。

## 可见性与状态动作

- `private`：模拟器持有的隐蔽事实，不能直接进入玩家新闻或人物公开介绍。
- `participants`：参与者能够经历或知道的事情；玩家仅认识其中一人，不等于自动获知全部过程。实际获知仍需来源规则。
- `public`：可通过公开记录或公开场合获取的事件；叙述中的核验、澄清和临时处理不是对所有未决指控的概括判决。
- `stat` 只改现金、健康、压力、声誉；`relation` 只改某个方向的信任、亲近、紧张；`flag` 和 `edge_flag` 记录个人事实与定向案件；`transfer` 在双方之间原子转账。
- 非现金数值单次变化绝对值不超过 30，现金／转账不超过 2000。转账来源必须有足额资金，量表仍须保持 0–100，现金不得为负。

## 覆盖和验证的限制

已检查字典计数与唯一 ID、职业／类别／性格路径引用、正向旗标来源、单次变化上限、转账角色，以及 8 项修复都读取并清除同方向案件旗标；已通过 `game.population.validate_library`。另用构造的合法局部人物状态调用实际引擎：32 项模板均成功试算，12 项带定向前事的模板在调换角色或移除关系旗标后被拒绝，32 项均拒绝已故目标参与。

这些是资产契约与局部反例检查，不能证明从随机初始人口自然到达全部 32 项互动。

当前的霸凌、腐败和包庇旗标没有各自完整的专用调查／修复链；它们允许成为未决经历，不能把尚未编写的后续当作已经处理。人格、动机、家务劳动、疾病、机构与法律程序仍是有界抽象，不覆盖所有身份、文化、关系形式、犯罪形态或人的一生。未模拟的细节不能靠叙述凭空补成既成事实。
