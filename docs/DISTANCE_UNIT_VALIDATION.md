# TASK-004 距离单位验证

> **终止说明（2026-07-20）**：专业货车API因最低采购成本过高，于2026-07-20终止，项目改用普通驾车参考距离。本文仅作为历史技术记录，不代表当前实现。

文档日期：2026-07-20  
结论：**未确认；禁止正式公里换算和 74 行批量**

## 当前执行状态

本机安全存储中没有高德 Web 服务 Key，因此真实 HTTP 调用次数为 0。下表不填充猜测值，不把普通驾车距离或模拟距离冒充为货车结果。

| 线路 | paths.distance 原始值 | steps.distance | steps 汇总 | 差异 | 假设为米的公里值 | 人工货车参考 | 结论 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| A 北京短途 size=2 | 未调用 | 未调用 | 未调用 | 未计算 | 未换算 | 待人工核对 | 未确认 |
| B 苏州太仓→南京 size=2 | 未调用 | 未调用 | 未调用 | 未计算 | 未换算 | 待人工核对 | 未确认 |
| C 西安→深圳 size=4 | 未调用 | 未调用 | 未调用 | 未计算 | 未换算 | 待人工核对 | 未确认 |

## 验证方法

高德[货车路径规划基础版文档](https://lbs.amap.com/api/logistic-service/guide/wagon_path/truck-route-plan-basis)明确标注 `steps.distance` 为米，但没有在 `paths.distance` 行直接标注单位。因此每条线路必须用 `nosteps=0` 记录：

```text
paths.distance
所有 steps.distance 原始值
sum(steps.distance)
absolute_difference = abs(paths.distance - sum(steps.distance))
relative_difference = absolute_difference / max(paths.distance, sum, 1)
```

通过条件采用任务批准的较宽松门：绝对差异不超过 500 米，或相对差异不超过 1%。三条线路都通过后，才可结合人工高德货车模式参考值形成单位结论。

代码已实现 `validate_path_against_steps()` 和唯一换算入口 `meters_to_kilometers()`；后者在单位未确认时抛出“距离单位未确认”，不会返回公里值。

## 待完成

1. 在本机界面安全保存 Key 并确认专业货车权限。
2. 对三条线路执行真实 `nosteps=0` 调用。
3. 用户按 `MANUAL_ROUTE_CHECKLIST.md` 填写高德地图货车模式参考值。
4. 复核三条差异后才可把本机批量门中的 `distance_unit_validated` 设为真。
