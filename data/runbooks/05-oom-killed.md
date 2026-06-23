# 容器 OOMKilled 排查

## 现象
Pod 反复重启，`kubectl describe` 显示 `Reason: OOMKilled`，退出码 137。服务间歇性不可用，常伴随流量高峰期。

## 常见根因
1. 内存泄漏：长期运行后堆内存持续增长，最终超过 limit 被 kill。
2. 大对象/大结果集：一次性加载全表或超大 JSON 到内存。
3. 内存 limit 设置过低，低于应用实际稳态需求。
4. 缓存无上限：本地缓存（如 Guava/Caffeine）无 size/weight 限制，无限增长。
5. 并发暴涨：突发流量导致同时处理大量请求，瞬时内存峰值超限。

## 排查步骤
1. 确认是 OOMKilled 而非应用 bug：describe 里看 Last State 的 Reason 和 Exit Code 137。
2. 对比内存 limit 与实际用量：监控里看工作内存是否长期贴近 limit。
3. 抓取堆 dump（JMAP / py-spy / pprof），分析大对象和泄漏引用链。
4. 查是否伴随流量高峰：内存峰值与 QPS 是否同步。
5. 审查缓存配置：本地缓存是否有大小/过期策略。

## 修复方案
- 泄漏：根据 dump 定位泄漏对象，修复引用未释放问题。
- 大对象：改分页/流式处理，避免一次性载入。
- limit：上调 memory limit（注意节点总量），并调大对应 request。
- 缓存：加上 size 上限和过期策略（如 LRU + TTL）。

## 预防措施
- 设置基于内存使用率的告警（如用量 > 80% 告警）。
- 本地缓存必须有上限策略，大缓存优先用 Redis。
- 上线前压测确认峰值内存，limit 预留 30% 余量。
