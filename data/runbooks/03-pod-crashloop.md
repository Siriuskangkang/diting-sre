# Pod CrashLoopBackOff 排查

## 现象
`kubectl get pods` 显示某 Pod 状态为 `CrashLoopBackOff`，RESTARTS 持续增加，服务无法稳定对外提供流量。

## 常见根因
1. 应用启动即崩溃：配置错误、依赖（DB/配置中心）连不上、端口冲突。
2. 存活探针（liveness probe）配置过严：启动慢于探针阈值，被反复 kill 重启。
3. 容器入口命令（command/args）写错，进程立即退出。
4. 资源限制过严：内存 limit 太小，启动期即 OOM。
5. 镜像或环境变量缺失：拉错 tag、缺少必需的 SECRET/CONFIGMAP。

## 排查步骤
1. `kubectl describe pod <name>` 看 Events，确认是 OOM、探针失败还是退出码非 0。
2. `kubectl logs <name> --previous` 查看上一次崩溃前的日志（关键，能看到崩溃原因）。
3. 检查 liveness/readiness 探针的 initialDelaySeconds 是否小于真实启动耗时。
4. 确认资源 requests/limits 是否合理，是否被 OOMKilled（describe 里有 OOMKilled）。
5. 核对配置：环境变量、ConfigMap/Secret 是否挂载正确，依赖地址是否可达。

## 修复方案
- 探针过严：调大 initialDelaySeconds / failureThreshold，或改用 readiness 代替 liveness。
- 启动崩溃：修复配置/依赖，确保启动期需要的资源都就绪。
- OOM：上调内存 limit 或排查内存泄漏。
- 镜像问题：回滚到上一个可用镜像 tag。

## 预防措施
- 探针参数基于真实启动耗时设置，上线前压测验证。
- 关键配置做启动期校验，缺失则 fail-fast 并输出清晰错误。
- 内存 limit 预留 30% 余量。
