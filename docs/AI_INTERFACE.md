# AI 工具接口

这是给外部 AI 客户端调用的确定性 HTTP 接口，非内置 LLM。API 不提供 Shell、文件路径写入、生产配置修改、模型晋级或交易工具。

## 本地启动

先生成本地随机令牌并仅放在当前进程环境：

```powershell
$env:MARKET_STATE_FILTER_API_TOKEN = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
.\.venv\Scripts\market-state-filter.exe serve --output outputs/demo --port 8765
```

不要在聊天、Git、日志中展示令牌。服务只绑定回环地址。所有请求都需要 `Authorization: Bearer <local token>`。

## 工具

| 方法与路径 | 行为 |
|---|---|
| GET `/api/tools` | 返回工具定义供 AI 客户端使用 |
| GET `/api/report` | 返回已有 `report.json`，没有报告时为 404 |
| GET `/api/tasks` | 返回最多 100 条已登记任务 |
| POST `/api/tasks` | 接受 `{"horizon":24,"seed":7}`，返回 201、REGISTERED、executed=false |

POST 仅接受这两个字段、JSON 对象、最多 4096 字节；horizon 为 1..96 整数，seed 为 0..2147483647 整数。任务持久化到服务输出目录的 tasks.sqlite3。没有自动消费者，用户审核后可通过本地 CLI 手工执行研究；任务状态暂不自动随 CLI 执行变化。

```powershell
$headers = @{Authorization="Bearer $env:MARKET_STATE_FILTER_API_TOKEN"}
Invoke-RestMethod http://127.0.0.1:8765/api/tools -Headers $headers
Invoke-RestMethod http://127.0.0.1:8765/api/tasks -Method Post -Headers $headers -ContentType application/json -Body '{"horizon":24,"seed":7}'
```

## 远程接入

接口保留远程统筹的接入点；本版本只实现本地认证服务。远程部署需要 HTTPS 反向代理、访问限制、请求限速和令牌管理。Python 标准库 HTTP 服务是开发用途，不作为生产公网服务。不要开放数据库或允许 AI 传入任意命令。后续自动执行研究需要独立权限、审计和资源限制设计。
