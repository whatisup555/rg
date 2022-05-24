# Charging in BUPT

## 智能充电桩调度计费系统详细需求

> 注：需求描述中所涉及的参数：快充电桩数(FastCharingPileNum)、慢充电桩数(TrickleChargingPileNum)、等候区车位容量(WaitingAreaSize)、充电桩排队队列长度(ChargingQueueLen)，在系统验收测试时可自由设置。

- 如图 1 所示，充电站分为“充电区”和“等候区”两个区域。电动车到达充电站后首先进入等候区，通过客户端软件向充电站（服务器端）提交充电请求。充电站（服务器端）根据请求充电模式的不同为客户分配两种类型排队号码：

  - 如果是请求“快充”模式，则号码首字母为 F，后续为 F 类型排队顺序号(从 1 开始，如 F1、F2)；

  - 如果是请求“慢充”模式，则号码首字母为 T，后续为 T 类型排队顺序号(从 1 开始，如 T1、T2)。此后，电动车在等候区等待叫号进入充电区。等候区最大车位容量为 N（N 的取值待进行系统测试时确定）。

- 充电区安装有 2 个快充电桩和 3 个慢充电桩，快充功率为 30 度/小时，慢充功率为 10 度/小时（系统验收时的测试数据可能会变化）。每个充电桩设置有等长的排队队列，长度为 M 个车位（M 的取值待进行系统测试时确定），队列排第一的车可充电。当任意充电桩队列存在空位时，充电站（系统服务器端）开始叫号，选取等候区排队号码和该充电桩模式匹配的第一辆车进入充电区(即快充桩对应 F 类型号码，慢充桩对应 T 类型号码)，并按照调度策略加入到匹配充电桩的排队队列中。

- 系统调度策略为：对应匹配充电模式下（快充/慢充），被调度车辆完成充电所需时长（等待时间+自己充电时间）最短。（等待时间=选定充电桩队列中所有车辆完成充电时间之和；自己充电时间=请求充电量/充电桩功率）

- 计费规则：

  - 总费用=充电费+服务费，充电费=单位电价**充电度数，服务费=服务费单价**充电度数。

  - 单位电价：随时间变化分为三类：

    - 峰时(1.0 元/度，10:00~15:00，18:00~21:00)；

    - 平时(0.7 元/度，7:00~10:00，15:00~18:00，21:00~23:00)；

    - 谷时(0.4 元/度，23:00~次日 7:00)。

  - 服务费单价：0.8 元/度

  - 充电时长（小时）=实际充电度数/充电功率(度/小时)

- 充电站计费调度系统由服务器端、用户客户端、管理员客户端组成。其中：

  - 服务器端需要具备的功能包括：用户信息维护；车辆排队号码生成；调度策略生成；计费；充电桩监控；数据统计（详单、报表数据生成）。

  - 用户客户端需要具备的功能包括：注册、登录；查看充电详单信息，至少包含如下字段：详单编号、详单生成时间、充电桩编号、充电电量、充电时长、启动时间、停止时间、充电费用、服务费用、总费用；提交或修改充电请求，包括充电模式（快充/慢充）、本次请求充电量；查看本车排队号码；查看本充电模式下前车等待数量；结束充电。

  - 管理员客户端需要具备的功能包括：启动/关闭充电桩；查看所有充电桩状态（各充电桩的当前状态信息（是否正常工作、系统启动后累计充电次数、充电总时长、充电总电量））；查看各充电桩等候服务的车辆信息（用户 ID、车辆电池总容量(度)、请求充电量(度)、排队时长）；报表展示，至少包含如下字段：时间(日、周、月)、充电桩编号、累计充电次数、累计充电时长、累计充电量、累计充电费用、累计服务费用、累计总费用。

- 用户修改请求场景。充电针允许客户在特殊状态下修改充电请求，场景如下：

  - 修改充电模式(快/慢充)

    - 允许在等候区修改，修改后重新生成排队号，并排到修改后对应模式类型队列的最后一位。

    - 不允许在充电区修改，可取消充电重新进入等候区排队。

  - 修改请求充电量

    - 允许在等候区修改，排队号不变

    - 不允许在充电区修改，可取消充电离开或重新进入等候区排队

  - 取消充电：等候区、充电区均允许

- 若充电桩出现故障(只考虑单一充电桩故障且正好该充电桩有车排队的情况)，则正在被充电的车辆停止计费，本次充电过程对应一条详单。此后系统重新为故障队列中的车辆进行调度。

  - 优先级调度：暂停等候区叫号服务，当其它同类型充电桩队列有空位时，优先为故障充电桩等候队列提供调度，待该故障队列中全部车辆调度完毕后，再重新开启等候区叫号服务。

  - 时间顺序调度：暂停等候区叫号服务，将其它同类型充电桩中尚未充电的车辆与故障候队列中车辆合为一组，按照排队号码先后顺序重新调度。调度完毕后，再重新开启等候区叫号服务。

  - 当充电桩故障恢复，若其它同类型充电桩中尚有车辆排队，则暂停等候区叫号服务，将其它同类型充电桩中尚未充电的车辆合为一组，按照排队号码先后顺序重新调度。调度完毕后，再重新开启等候区叫号服务。

- 扩展调度请求(选做，可加分)

  - 单次调度总充电时长最短：当充电区出现多个车辆空位时，系统可一次同时叫多个号，此时进入充电区的多辆车不考虑排队先后顺序，调度策略为：

    - 按充电模式分配对应充电桩；
    - 满足进入充电区的多辆车完成充电总时长(所有车累计等待时间+累计充电时间)最短。

  - 批量调度总充电时长最短：为了提高效率，假设只有当到达充电站的车辆等于全部车位数量(充电区+等候区)时，才开始进行一次批量调度充电，完成之后再进行下一批。规定在一次批量调度中不区分快充和慢充模式以及车辆到达的先后顺序，客户请求只需要指定充电量大小，系统调度策略为：

    - 所有车辆均可分配任意类型充电桩；
    - 满足一批车辆完成充电总时长(所有车累计等待时间+累计充电时间)最短。

  - 以上两种调度方式均不考虑客户修改充电请求以及充电桩出现故障等特殊情况。