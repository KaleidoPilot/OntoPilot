---

---

name

template-abb245cc921144d2814488cb

description

通用经营分析报告

# 通用经营分析报告

基于ERP或业务系统数据，对销售、商品、客户、供应商及库存进行多维度诊断，识别经营风险与结构问题，为管理层提供决策依据。

根据本次资料分析和写作。示例主题和实体不作为必填目标；不能推导的内容省略并单独提示，不能凭空编造。

## 一、报告概要

这一部分的作用：界定分析边界，明确统计口径，并提炼核心结论以引导读者关注重点。

首先说明数据来源（如系统记录）、统计截止时间及覆盖的业务实体范围（如订单数、SKU数）。其次解释关键指标的计算逻辑（如毛利定义、是否含取消订单等）。最后，用精炼的语言概括本期经营的3-4个核心特征（如规模、集中度、资金效率、流程瓶颈），直接点出主要矛盾。

呈现形式：正文

### 数据来源与取数口径

| 资料需求     | 项目组     | 表 · 字段                                 | 方式与口径 |
| :------- | :------ | :------------------------------------- | :---- |
| 统计周期起止时间 | erp测试商品 | virtual\_erp.sales\_orders.order\_date | 直接取值  |

未匹配来源的信息由用户补充资料；不能沿用模板旧值或编造。

## 二、经营总览

这一部分的作用：展示整体业绩表现，通过关键指标对比和订单概况建立宏观认知。

使用表格列出销售额、毛利、毛利率、客单价、库存占用等核心KPI，并附带简要说明（如行业水平对比或环比变化）。随后简述订单的整体分布情况，包括有效/取消比例、金额区间分布，判断是否存在极端值或结构性失衡。

呈现形式：表格、正文

### 数据来源与取数口径

| 资料需求         | 项目组     | 表 · 字段                                                                                                         | 方式与口径                                                                                                                                                                  |
| :----------- | :------ | :------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 总销售额、总毛利、毛利率 | erp测试商品 | virtual\_erp.sales\_order\_items.amount；virtual\_erp.sales\_order\_items.qty；virtual\_erp.products.cost\_price | 推导：总销售额=SUM(sales\_order\_items.amount)；总毛利=SUM(sales\_order\_items.amount - sales\_order\_items.qty \* products.cost\_price)；毛利率=总毛利/总销售额。需关联订单明细与商品表获取成本价，并过滤有效状态订单。 |
| 平均客单价、平均件均价  | erp测试商品 | virtual\_erp.sales\_orders.total\_amount；virtual\_erp.sales\_order\_items.unit\_price                          | 推导：平均客单价=SUM(sales\_orders.total\_amount)/COUNT(DISTINCT sales\_orders.id)；平均件均价=AVG(sales\_order\_items.unit\_price)。需过滤有效状态订单。                                       |
| 有效订单数、取消订单数  | erp测试商品 | virtual\_erp.sales\_orders.status；virtual\_erp.sales\_orders.id                                                | 推导：根据sales\_orders.status字段分类统计订单数量。                                                                                                                                   |
| 单笔订单金额分布数据   | erp测试商品 | virtual\_erp.sales\_orders.total\_amount                                                                       | 推导：对sales\_orders.total\_amount进行分桶统计（如区间分组），需过滤有效状态订单。                                                                                                                |

## 三、销售订单分析

这一部分的作用：深入剖析订单细节，揭示交易行为背后的构成逻辑与流转效率。

分四个维度展开：1. **规模与分布**：列表展示各订单金额及占比，分析极差与均值关系；2. **构成**：拆解订单内的商品组合（品项数、件数），指出“件数与金额不成正比”等潜在成本陷阱；3. **流转**：统计各状态（待处理、已付款、发货等）的订单数量与金额，识别流程停滞环节；4. **取消**：单独分析取消订单的原因及其对特定品类或库存的连锁影响。

呈现形式：表格、列表、正文

### 数据来源与取数口径

| 资料需求                  | 项目组     | 表 · 字段                                                                                                                                                                                  | 方式与口径 |
| :-------------------- | :------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---- |
| 订单明细（ID、客户、金额、状态、时间戳） | erp测试商品 | virtual\_erp.sales\_orders.id；virtual\_erp.sales\_orders.customer\_id；virtual\_erp.sales\_orders.total\_amount；virtual\_erp.sales\_orders.status；virtual\_erp.sales\_orders.created\_at | 直接取值  |
| 订单行项目（商品、数量、单价）       | erp测试商品 | virtual\_erp.sales\_order\_items.product\_id；virtual\_erp.sales\_order\_items.qty；virtual\_erp.sales\_order\_items.unit\_price                                                          | 直接取值  |
| 取消订单的具体原因或备注          | erp测试商品 | virtual\_erp.sales\_orders.remark                                                                                                                                                       | 直接取值  |

## 四、商品分析

这一部分的作用：评估商品的销售贡献、盈利能力及生命周期状态，优化产品组合。

呈现形式：表格、正文

### 数据来源与取数口径

| 资料需求              | 项目组     | 表 · 字段                                                                                                         | 方式与口径                                                                                                   |
| :---------------- | :------ | :------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------ |
| 商品维度的销量、销售额、成本、毛利 | erp测试商品 | virtual\_erp.sales\_order\_items.qty；virtual\_erp.sales\_order\_items.amount；virtual\_erp.products.cost\_price | 推导：按product\_id分组：销量=SUM(qty)，销售额=SUM(amount)，成本=SUM(qty\*cost\_price)，毛利=销售额-成本。需关联订单明细与商品表，并过滤有效状态订单。 |
| 商品分类信息            | erp测试商品 | virtual\_erp.products.category                                                                                 | 直接取值                                                                                                    |
| 库存中各商品的当前数量与价值    | erp测试商品 | virtual\_erp.products.stock\_qty；virtual\_erp.products.cost\_price；virtual\_erp.products.sale\_price           | 推导：当前数量=stock\_qty；库存成本价值=stock\_qty*cost\_price；库存销售货值=stock\_qty*sale\_price。                         |

## 五、客户分析

这一部分的作用：衡量客户价值贡献，评估收入稳定性与客户依赖风险。

呈现形式：表格、正文

### 数据来源与取数口径

| 资料需求             | 项目组     | 表 · 字段                                                                                                                                                       | 方式与口径                                                                                                                |
| :--------------- | :------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------- |
| 客户维度的交易汇总数据      | erp测试商品 | virtual\_erp.sales\_orders.customer\_id；virtual\_erp.sales\_orders.total\_amount；virtual\_erp.sales\_orders.id                                               | 推导：按customer\_id分组：订单数=COUNT(id)，销售额=SUM(total\_amount)。需过滤有效状态订单。                                                   |
| 客户建档时间与首次/最近交易时间 | erp测试商品 | virtual\_erp.customers.created\_at；virtual\_erp.sales\_orders.order\_date                                                                                    | 推导：建档时间=customers.created\_at；首次交易时间=MIN(sales\_orders.order\_date)；最近交易时间=MAX(sales\_orders.order\_date)。需关联客户与订单表。 |
| 客户订单历史序列         | erp测试商品 | virtual\_erp.sales\_orders.customer\_id；virtual\_erp.sales\_orders.order\_no；virtual\_erp.sales\_orders.order\_date；virtual\_erp.sales\_orders.total\_amount | 直接取值                                                                                                                 |

## 六、供应商分析

这一部分的作用：审查供应链资源的有效性，验证采购业务与实际交易的关联性。

呈现形式：表格、正文

### 数据来源与取数口径

| 资料需求    | 项目组     | 表 · 字段                                                                                                                                                                           | 方式与口径 |
| :------ | :------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---- |
| 供应商基础档案 | erp测试商品 | virtual\_erp.suppliers.code；virtual\_erp.suppliers.name；virtual\_erp.suppliers.contact；virtual\_erp.suppliers.phone；virtual\_erp.suppliers.address；virtual\_erp.suppliers.status | 直接取值  |

## 七、库存分析

这一部分的作用：监控库存结构与资金效率，预警积压风险与缺货隐患。

呈现形式：表格、正文

### 数据来源与取数口径

| 资料需求         | 项目组     | 表 · 字段                                                                                                                                                                                | 方式与口径                                                                 |
| :----------- | :------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------- |
| 各商品当前库存数量与单价 | erp测试商品 | virtual\_erp.products.stock\_qty；virtual\_erp.products.cost\_price；virtual\_erp.products.sale\_price                                                                                  | 直接取值                                                                  |
| 安全库存设定值      | erp测试商品 | virtual\_erp.products.safety\_stock                                                                                                                                                   | 直接取值                                                                  |
| 期间内出入库流水明细   | erp测试商品 | virtual\_erp.stock\_logs.product\_id；virtual\_erp.stock\_logs.change\_qty；virtual\_erp.stock\_logs.change\_type；virtual\_erp.stock\_logs.ref\_no；virtual\_erp.stock\_logs.created\_at | 直接取值                                                                  |
| 期间内销售数量      | erp测试商品 | virtual\_erp.sales\_order\_items.qty；virtual\_erp.sales\_orders.order\_date；virtual\_erp.sales\_orders.status                                                                         | 推导：SUM(sales\_order\_items.qty)，需关联订单表并按order\_date过滤期间及status过滤有效订单。 |

## 八、经营诊断

这一部分的作用：综合前述分析，提炼核心问题并按优先级排序，形成行动指南。

呈现形式：表格、正文

### 数据来源与取数口径

未匹配来源的信息由用户补充资料；不能沿用模板旧值或编造。

## 九、结论

这一部分的作用：总结全文，重申经营现状的本质特征，给出最终的管理建议方向。

回顾核心财务数据，定性评价盈利能力与规模现状。分别简述商品、客户、供应商、库存四大维度的最终状态（如“结构集中”、“环节空转”、“资金沉淀”）。最后，指出当前最直接的着力点（如处置滞销库存、推进停滞订单），强调业务闭环的完整性与起步阶段的特殊性。

呈现形式：正文

### 数据来源与取数口径

## 全文规则

## 模板结构与排版

称谓、开场、正文、结语与落款各归其位，不将它们分别扩成编号章节。章节以模板原层级为准，新资料放入相应部分。

## 生成与核对

## 图表输出约定

使用 Markdown 表格保存数据。图表声明放在 chart 代码块内，table 从1开始、列从0开始，柱状图/折线图/饼图读取该表而非另一组数字：

```chart
{"type":"bar","table":1,"title":"指标对比","xColumn":0,"yColumns":[1]}
```

type 可为 bar、line、pie；有明确流程依据时可使用 flow，提供 nodes（id、label）和 edges（source、target）。不得用“此处插图”冒充已生成图表。

## 项目组取数约定

只使用本Skill列明且执行时仍有权限的表字段和已登记关系。根据用户需求确定主体、期间、单位和筛选条件，运行时复核结构；本Skill不包含已查询的业务数值。SQL生成与执行由聊天流程负责，不将字段映射当成事实。
