# RCA-Agent on RCA-100 实验记录

## 环境信息

- **模型**：gpt-4o
- **Python**：3.10（conda openrca100）
- **关键依赖**：openai==1.54.3, httpx==0.27.2, pandas, pyarrow, tiktoken

## 已完成的代码适配

| 文件 | 改动 |
|---|---|
| `main/evaluate.py` | 新增 `evaluate_rca100()` 函数，解析 agent 输出的 `root_cause_entities` / `root_cause_types` 与 gt.json 做精确匹配 |
| `rca/run_agent_standard.py` | 加载 `rca100/answer_key/` 为 gt dict；rca100 分支调用 `evaluate_rca100()`；instruction 前注入 `[Task directory: ...]` |
| `rca/baseline/rca_agent/controller.py` | 支持 `bp.summary` 自定义 summary 模板；修复 `response_raw` 未赋值 bug |
| `rca/baseline/rca_agent/prompt/basic_prompt_rca100.py` | 新增 rca100 专属 summary 模板；补充 task.json 字段、XML 标签解析提示、诊断工作流、类型转换提示 |

## 实验结果

### Run 1：t001 单任务（2026-06-13_08-02-13）✅ 满分

- **Score：1.0**
- entity: `payment` ✅，type: `httpError5xx` ✅
- 9 步完成，无报错
- Agent 完整走了 metrics → traces → logs 分析流程

### Run 2：5 任务批量（2026-06-13_08-09-30）

| Task | Score | 预测 Entity | 真值 Entity | 预测 Type | 真值 Type | 分析状态 |
|---|---|---|---|---|---|---|
| t001 | 0.0 | checkout | payment | memoryPressure | httpError5xx | ✅ 完整分析 |
| t002 | 0.0 | cart | cart-64944cd445-8pbgx | — | redisUnavailable | ✅ 完整分析 |
| t003 | 0.0 | frontend-proxy | cn-hongkong.10.0.1.69 | — | nodeMemoryOOM | ⚠️ token 溢出 |
| t004 | 0.0 | cart | checkout | — | trafficSurge | ⚠️ token 溢出 |
| t005 | 0.0 | checkout | cn-hongkong.10.0.1.107 | — | nodeCpuHigh | ✅ 完整分析 |

### Run 3：t001 重跑（2026-06-13_08-26-05）

- **Score：0.5**
- entity: `payment` ✅，type: `slowSQL` ❌（真值 `httpError5xx`）
- 有 token 溢出警告

## 统计

| 指标 | 值 |
|---|---|
| 完成分析的 case 数 | 8 个（t001 × 3 + t002-t005 各 1） |
| 得分 > 0 的 | 2 个（t001 的 2 次运行） |
| 得分 = 0 的 | 6 个 |
| 准确率（>0 分） | 2/8 = 25% |

## RCA-100 Ground Truth 分布

| Entity 类型 | 数量 | 示例 |
|---|---|---|
| service | 83 | payment, checkout, cart, inventory 等 11 个服务 |
| node | 17 | cn-hongkong.10.0.1.107 等 7 个节点 IP |
| pod | 3 | cart-64944cd445-8pbgx, inventory-5c4b7bcb9c-d24qh |

## 已知问题

### 1. 评分匹配太严格
- 真值是 pod 名 `cart-64944cd445-8pbgx`，agent 输出服务名 `cart`，精确匹配得 0 分
- 真值是 node IP，agent 输出服务名，无法匹配
- **建议**：评分改为模糊匹配（entity 名包含关系）

### 2. Token 溢出
- `Token length exceeds the limit: 54726`，超过 16384 上限
- 查询返回数据太多，executor 被迫截断，导致分析不充分
- **建议**：在 executor rules 中限制查询返回行数

### 3. LLM 不稳定
- t001 在不同运行中得分 0.0 / 0.5 / 1.0，结果不可复现
- **建议**：设置 temperature=0 或多次采样取最优

### 4. Node/Pod 级别定位能力不足
- Agent 几乎总是输出 service 级别 entity
- 17% 的 case 根因在 node/pod 级别，agent 缺乏分析到该粒度的能力
- **建议**：在 agent_prompt 中增加 node/pod 级别的诊断规则

## 运行命令

```bash
# 单任务测试
python rca/run_agent_standard.py \
  --dataset rca100 \
  --start_idx 0 --end_idx 0 \
  --controller_max_step 10 \
  --timeout 600

# 全量运行（后台）
nohup python rca/run_agent_standard.py \
  --dataset rca100 \
  --start_idx 0 --end_idx 102 \
  --controller_max_step 25 \
  --timeout 900 \
  > rca100_full.log 2>&1 &

# 查看结果
cat test/result/rca100/agent-rca-gpt-4o.csv
```
