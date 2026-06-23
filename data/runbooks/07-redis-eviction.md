# Redis 内存满与大量驱逐（eviction）排查

## 现象
Redis 监控显示 `evicted_keys` 持续快速增长，`used_memory` 接近 `maxmemory`，应用出现缓存命中率骤降、延迟上升，甚至偶发读取不到数据。

## 常见根因
1. 缓存未设置 TTL，冷数据无限堆积撑爆内存。
2. 大 key（如包含百万元素的 Hash/Set/ZSet）占用过多内存。
3. maxmemory 设置不合理，或淘汰策略（maxmemory-policy）不符合业务预期。
4. 热点 key 过期后引发缓存击穿，瞬时大量请求穿透到 DB。
5. 写入速率远超淘汰速率，内存持续上涨。

## 排查步骤
1. `INFO memory` 看 used_memory / maxmemory / 内存碎片率（mem_fragmentation_ratio）。
2. `INFO stats` 看 evicted_keys 增速和 expired_keys。
3. 用 `redis-cli --bigkeys` 或内存分析工具（如 RAMP）定位大 key 和热点 key。
4. 抽样检查是否有大量 key 未设置 TTL：`TTL <key>` 抽查，或用 SCAN 统计 TTL 分布。
5. 确认 maxmemory-policy（allkeys-lru / volatile-lru / noeviction）是否匹配业务可接受的数据丢失范围。

## 修复方案
- 立即扩容：提升 maxmemory 或扩容 Redis 实例规格，止血。
- 大 key：拆分（Hash 分桶）或迁移到其他存储，避免单 key 过大。
- TTL：给所有缓存 key 加合理的过期时间，杜绝永不过期。
- 击穿：热点 key 加互斥锁或逻辑过期，防止同时回源。

## 预防措施
- 所有缓存 key 必须有 TTL，默认上限 + 按业务差异化。
- 上线前评估大 key，禁止单 key 超过设定阈值（如 10MB）。
- 配置内存使用率和驱逐速率告警。
