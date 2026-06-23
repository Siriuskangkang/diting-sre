# TLS 证书过期导致服务不通排查

## 现象
某服务突然对所有调用方返回错误，日志或客户端报 "certificate has expired" / "x509: certificate signed by unknown authority" / "SSLHandshakeException"。常发生在凌晨或固定时间点（证书到期的同一时刻）。

## 常见根因
1. 服务器侧 / Ingress / 负载均衡的 TLS 证书到期未续期。
2. 客户端信任的 CA 证书库未包含新签发证书的根 CA。
3. 容器/系统时间不准（时钟漂移），导致证书被判定为"尚未生效"或"已过期"。
4. 证书自动续期任务（如 cert-manager）失败未告警。
5. 证书链不完整（缺少中间证书），部分客户端校验失败。

## 排查步骤
1. 确认错误是否精确指向证书过期：看完整错误信息（expired / unknown CA / not yet valid）。
2. 用 `openssl s_client -connect host:443` 查看服务端证书的有效期和证书链。
3. `echo | openssl s_client -connect host:443 2>/dev/null | openssl x509 -noout -dates` 直接看起止时间。
4. 检查自动续期组件状态：cert-manager 的 Certificate 资源、Order/Challenge 是否失败。
5. 确认节点时间：`date` / `chronyc tracking`，排查时钟漂移。

## 修复方案
- 紧急：手动续期并重新部署证书（kubectl 更新 Secret / Ingress 重载）。
- CA 不信任：更新客户端信任库，或确认签发 CA 与预期一致。
- 时钟漂移：同步系统时间（NTP / chrony），消除漂移。
- 证书链：补全中间证书，重新打包 fullchain。

## 预防措施
- 证书到期前 30/14/7 天分级告警，覆盖续期失败场景。
- 关键证书用 cert-manager 自动续期 + 续期失败告警。
- 节点时间统一用 NTP 同步，纳入监控。
