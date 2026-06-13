# RCA-Agent 详细工作原理分析

## 📋 目录
1. [系统架构概览](#1-系统架构概览)
2. [Controller 深度分析](#2-controller-深度分析)
3. [Executor 深度分析](#3-executor-深度分析)
4. [完整 Prompt 约束体系](#4-完整-prompt-约束体系)
5. [错误处理与回溯机制](#5-错误处理与回溯机制)
6. [实际运行示例](#6-实际运行示例)

---

## 1. 系统架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RCA-Agent 总体架构                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐ │
│  │   Controller │◄───────►│   Executor   │◄───────►│ IPython      │ │
│  │   (推理)     │  指令   │   (写代码)   │  执行   │   Kernel     │ │
│  └──────────────┘  结果   └──────────────┘         └──────────────┘ │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────┐                                                   │
│  │   最终答案   │                                                   │
│  └──────────────┘                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 主要模块

| 模块 | 文件 | 功能 |
|------|------|------|
| Controller | `controller.py` | 负责推理分析、生成指令、控制流程 |
| Executor | `executor.py` | 负责将指令转化为Python代码并执行 |
| Agent核心 | `rca_agent.py` | 简单的封装，调用controller循环 |
| 运行入口 | `run_agent_standard.py` | 任务调度、评估、结果保存 |

---

## 2. Controller 深度分析

### 2.1 Controller 角色定位

Controller 被设定为 **DevOps故障诊断系统管理员**，其核心职责：

```python
system = """You are the Administrator of a DevOps Assistant system for failure diagnosis.
To solve each given issue, you should iteratively instruct an Executor to write and execute Python code
for data analysis on telemetry files of target system. By analyzing the execution results, you should
approximate the answer step-by-step."""
```

### 2.2 响应格式约束

Controller的每一步响应必须严格遵循JSON格式：

```json
{
    "analysis": (对Executor上一步执行结果的分析，详细推理'已完成什么'和'能推断出什么'。如果是第一步，响应'None'。),
    "completed": ("True" 如果你认为问题已解决，可以在'instruction'字段中得出答案。否则 "False"。),
    "instruction": (你对Executor的指令，通过代码执行进行下一步。不要涉及复杂的多步指令。保持原子性，清晰说明'做什么'和'怎么做'。如果你认为问题已解决，自己写一个总结。)
}
```

**关键约束**：
- 必须使用JSON，不能有任何markdown标签
- 使用`\n`代替实际换行确保JSON兼容性
- 必须包含三个字段：`analysis`, `completed`, `instruction`

### 2.3 控制循环流程

```
for step in range(max_step):  # 最多25步
    ┌───────────────────────────────────────────────────────────┐
    │ 1. Controller分析上一步结果                               │
    │    - 理解已完成的分析                                     │
    │    - 推断下一步需要做什么                                 │
    └───────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────────────┐
    │ 2. 检查是否完成 (completed == "True")?                   │
    │    - 是 → 进入最终答案生成阶段                           │
    │    - 否 → 继续                                            │
    └───────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────────────┐
    │ 3. 生成Executor指令 (保持原子性)                          │
    │    - 明确"做什么"                                         │
    │    - 明确"怎么做"                                         │
    │    - 一次只做一件事                                       │
    └───────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────────────┐
    │ 4. 将指令发送给Executor执行                               │
    └───────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────────────┐
    │ 5. 记录执行结果到trajectory                               │
    └───────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────────────┐
    │ 6. 将结果反馈给Controller继续循环                         │
    └───────────────────────────────────────────────────────────┘
```

### 2.4 最终答案生成

当Controller认为任务完成时，进入最终答案阶段：

```python
summary = """Now, you have decided to finish your reasoning process. You should now provide the final answer to the issue. 
The candidates of possible root cause components and reasons are provided to you. 
The root cause components and reasons must be selected from the provided candidates.

{cand}

Recall the issue is: {objective}

Please first review your previous reasoning process to infer an exact answer of the issue. 
Then, summarize your final answer of the root causes using the following JSON format at the end of your response:

```json
{{
    "1": {{
        "root cause occurrence datetime": (if asked by the issue, format: '%Y-%m-%d %H:%M:%S', otherwise ommited),
        "root cause component": (if asked by the issue, one selected from the possible root cause component list, otherwise ommited),
        "root cause reason": (if asked by the issue, one selected from the possible root cause reason list, otherwise ommited),
    }}, 
    ...
}}
```

Note that all the root cause components and reasons must be selected from the provided candidates. 
Do not reply 'unknown' or 'null' or 'not found' in the JSON. 
Do not be too conservative in selecting the root cause components and reasons. 
Be decisive to infer a possible answer based on your current observation."""
```

**关键约束**：
- 必须从候选列表中选择组件和原因
- 不能返回'unknown'或'null'
- 要有决断性，不要过于保守
- 只返回问题要求的字段

### 2.5 Controller 推理规则 (agent_prompt.py)

这是Controller的核心知识库，包含9条"应该做"和9条"不应该做"的规则。

#### 应该做的事情 (What you SHOULD do):

**1. 遵循标准故障诊断工作流：`preprocess → anomaly detection → fault identification → root cause localization`**

1.1 **预处理 (Preprocess)**:
   - 聚合每个可能的根因组件的每个KPI，获得按'component-KPI'分类的多个时间序列
   - 计算每个'component-KPI'时间序列的全局阈值（如全局P95）
   - 过滤给定时间范围内的数据进行进一步分析
   - 只关注可能的根因组件，忽略其他层次的组件

1.2 **异常检测 (Anomaly Detection)**:
   - 异常通常是超过全局阈值的数据点
   - 在流量KPI或业务KPI中，也要寻找低于某个阈值的异常（如<=P95, <=P15, <=P5）
   - 如果确实找不到异常，可以放宽全局阈值

1.3 **故障识别 (Fault Identification)**:
   - '故障'是特定component-KPI时间序列的连续子序列
   - 过滤掉孤立的噪声尖峰来定位故障
   - 排除那些子序列中的最大/最小值仅轻微超过/低于阈值的情况（很可能是误报）

1.4 **根因定位 (Root Cause Localization)**:
   - 根因的发生时间、组件、原因可以从该故障的第一个数据点得出
   - 如果在不同层次识别到多个故障组件，且问题描述是单一故障，根因层次由偏离阈值最显著的故障决定
   - 如果在同一层次有多个故障组件，使用traces和logs来识别根因组件
   - 在调用链中，根因组件通常是最后一个（最下游的）**故障**服务
   - 如果只有一个组件的一个资源KPI在特定时间有一个故障，那个故障就是根因

**2. 遵循分析顺序：`threshold calculation -> data extraction -> metric analysis -> trace analysis -> log analysis`**

2.0 **分析前**：先计算全局阈值，再提取和过滤故障持续时间内的数据
2.1 **指标分析**：使用指标计算每个组件的每个KPI是否有连续异常超过全局阈值，这是最快找到故障的方法
2.2 **追踪分析**：当指标分析在同一层次识别到多个故障组件时，使用traces进一步定位
2.3 **日志分析**：当指标分析识别到一个组件的多个故障资源KPI时，使用logs进一步定位资源
2.4 **确认有效性**：当Executor的检索结果为空时，总是确认目标键或字段是否有效

#### 不应该做的事情 (What you SHOULD NOT do):

1. ❌ **不要在响应中包含任何编程语言（Python）**，应该用自然语言提供有序步骤列表
2. ❌ **不要自己转换时间戳和datetime**，这些细节由Executor处理
3. ❌ **不要使用局部数据（特定时间范围内的过滤/缓存序列）计算全局阈值**，总是使用整个KPI序列来计算阈值
4. ❌ **不要通过Python可视化数据或画图**，Executor只能提供文本结果
5. ❌ **不要在本地文件系统中保存任何东西**，只在IPython Kernel中缓存中间结果
6. ❌ **不要在过滤数据后计算阈值**，总是先计算全局阈值再过滤
7. ❌ **不要在不知道哪些KPI可用的情况下查询特定KPI**，先确保你知道所有可用的KPI
8. ❌ **不要错误地将trace下游的健康服务识别为根因**，根因组件必须首先是通过指标分析识别出的故障组件
9. ❌ **不要在日志分析中只关注警告或错误日志**，许多info日志也包含有价值的信息

---

## 3. Executor 深度分析

### 3.1 Executor 角色定位

Executor 被设定为 **DevOps代码编写助手**，其核心职责：

```python
system = """You are a DevOps assistant for writing Python code to answer DevOps questions.
For each question, you need to write Python code to solve it by retrieving and processing telemetry data
of the target system. Your generated Python code will be automatically submitted to a IPython Kernel.
The execution result output in IPython Kernel will be used as the answer to the question."""
```

### 3.2 响应格式约束

Executor的响应必须严格遵循Python代码块格式：

```python
```python
(YOUR CODE HERE)
```
```

### 3.3 代码编写规则 (10条核心规则)

| 规则 | 详细说明 |
|------|---------|
| **1. 变量复用** | 尽可能复用变量以提高执行效率，因为IPython Kernel是有状态的 |
| **2. 显示结果** | 使用变量名而不是`print()`来显示结果。如果要显示多个变量，用逗号分隔，如`var1, var2` |
| **3. 数据处理** | 使用pandas DataFrame来处理和显示表格数据以提高效率和简洁性 |
| **4. 错误处理** | 如果遇到错误或意外结果，通过参考给出的IPython Kernel错误消息重写代码 |
| **5. 真实数据** | 不要模拟任何虚拟情况或假设任何未知事物。解决真实问题 |
| **6. 内存缓存** | 不要在磁盘中存储任何数据，只在内存中将数据缓存为变量 |
| **7. 无可视化** | 不要通过Python可视化数据或画图，只能提供文本结果，不要包含matplotlib或seaborn |
| **8. 纯代码** | 除了指令告诉你'使用纯英文'，不要生成Python代码块以外的任何东西 |
| **9. 阈值计算** | 不要在过滤给定持续时间内的数据后计算阈值。总是先使用特定组件在指标文件中的整个KPI序列计算全局阈值 |
| **10. 时区** | 所有问题使用**UTC+8**时间，请显式使用`pytz.timezone('Asia/Shanghai')`设置时区 |

### 3.4 Executor 执行流程

```
Executor.execute_act(instruction):
    │
    ├─ 1. 初始化系统提示（包含规则、背景、格式）
    │
    ├─ 2. 将指令添加到对话历史
    │
    ├─ 3. 循环最多2次重试
    │      │
    │      ├─ 3.1 调用大模型生成Python代码
    │      │
    │      ├─ 3.2 提取代码块（```python ... ```）
    │      │
    │      ├─ 3.3 检查是否包含matplotlib/seaborn（禁止）
    │      │
    │      ├─ 3.4 在IPython Kernel中执行代码
    │      │
    │      ├─ 3.5 检查执行状态
    │      │      │
    │      │      ├─ ✅ 成功:
    │      │      │    │
    │      │      │    ├─ 获取结果
    │      │      │    ├─ 检查token长度（>16384则继续）
    │      │      │    ├─ 对大数据框添加截断警告
    │      │      │    ├─ 调用大模型总结结果为简洁英文
    │      │      │    └─ 返回代码+总结结果+状态
    │      │      │
    │      │      └─ ❌ 失败:
    │      │           │
    │      │           ├─ 捕获错误traceback
    │      │           ├─ 添加到对话历史
    │      │           ├─ 要求重写并重试
    │      │           └─ 设置重试标志
    │      │
    │
    └─ 4. 如果2次都失败
           └─ 返回错误消息
```

### 3.5 结果处理与总结

执行成功后，Executor会进行**双重处理**：

1. **原始执行结果**：IPython Kernel的直接输出
2. **总结性描述**：调用另一个LLM调用将结果总结为简洁的英文

```python
summary = """The code execution is successful. The execution result is shown below: 

{result}

Please summarize a straightforward answer to the question based on the execution results. Use plain English."""
```

这样Controller就能更容易理解和分析结果，而不是直接面对原始的代码输出。

### 3.6 大数据框截断处理

当pandas DataFrame行数超过10行时，Executor会自动添加警告：

```python
**Note**: The printed pandas DataFrame is truncated due to its size. Only **10 rows** are displayed, which may introduce observation bias due to the incomplete table. If you want to comprehensively understand the details without bias, please ask Executor using `df.head(X)` to display more rows.
```

这提示Controller可能需要更详细的数据，可以要求Executor显示更多行。

---

## 4. 完整 Prompt 约束体系

### 4.1 系统架构约束

整个系统通过多层Prompt约束确保行为一致性：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Prompt 约束层级架构                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. 任务背景知识 (basic_prompt_X.py)                          │  │
│  │    - 遥测目录结构                                            │  │
│  │    - 数据模式 (schema)                                       │  │
│  │    - 可能的根因组件列表 (candidates)                         │  │
│  │    - 可能的根因原因列表                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│  ┌───────────────────────────┴───────────────────────────────────┐ │
│  │ 2. 故障诊断规则 (agent_prompt.py)                            │ │
│  │    - 标准工作流 (preprocess → anomaly detection → ...)      │ │
│  │    - 分析顺序 (metric → trace → log)                        │ │
│  │    - 根因定位策略                                           │ │
│  │    - 禁忌事项                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│  ┌───────────────────────────┴───────────────────────────────────┐ │
│  │ 3. 代码编写规则 (executor.py:rule)                          │ │
│  │    - IPython Kernel最佳实践                                  │ │
│  │    - 变量复用                                               │ │
│  │    - 时区处理                                               │ │
│  │    - 阈值计算要求                                           │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│  ┌───────────────────────────┴───────────────────────────────────┐ │
│  │ 4. 格式约束 (JSON/代码块)                                    │ │
│  │    - Controller: 严格JSON响应                               │ │
│  │    - Executor: Python代码块                                │ │
│  │    - 最终答案: 带markdown的JSON                             │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据Schema约束 (以Bank数据集为例)

#### 4.2.1 遥测目录结构

```
dataset/Bank/telemetry/
├── 2021_03_04/
│   ├── metric/
│   │   ├── metric_app.csv
│   │   └── metric_container.csv
│   ├── trace/
│   │   └── trace_span.csv
│   └── log/
│       └── log_service.csv
└── 2021_03_05/
    └── ...
```

#### 4.2.2 指标数据 (Metric)

**metric_app.csv** - 应用级KPI：
```csv
timestamp,rr,sr,cnt,mrt,tc
1614787440,100.0,100.0,22,53.27,ServiceTest1
```

字段说明：
- `rr`: 请求响应率
- `sr`: 成功率
- `cnt`: 计数
- `mrt`: 平均响应时间
- `tc`: 目标组件

**metric_container.csv** - 容器/组件级KPI：
```csv
timestamp,cmdb_id,kpi_name,value
1614787200,Tomcat04,OSLinux-CPU_CPU_CPUCpuUtil,26.2957
```

#### 4.2.3 追踪数据 (Trace)

**trace_span.csv** - 分布式追踪：
```csv
timestamp,cmdb_id,parent_id,span_id,trace_id,duration
1614787199628,dockerA2,369-bcou-dle-way1-c514cf30-43410@0824-2f0e47a816-17492,21030300016145905763,gw0120210304000517192504,19
```

**注意**：trace的timestamp单位是**毫秒**

#### 4.2.4 日志数据 (Log)

**log_service.csv** - 服务日志：
```csv
log_id,timestamp,cmdb_id,log_name,value
8c7f5908ed126abdd0de6dbdd739715c,1614787201,Tomcat01,gc,"3748789.580: [GC (CMS Initial Mark) ...]"
```

**注意**：log的timestamp单位是**秒**

#### 4.2.5 候选根因组件 (Bank)

```
- apache01, apache02
- Tomcat01, Tomcat02, Tomcat03, Tomcat04
- MG01, MG02
- IG01, IG02
- Mysql01, Mysql02
- Redis01, Redis02
```

#### 4.2.6 候选根因原因 (Bank)

```
- high CPU usage
- high memory usage
- network latency
- network packet loss
- high disk I/O read usage
- high disk space usage
- high JVM CPU load
- JVM Out of Memory (OOM) Heap
```

---

## 5. 错误处理与回溯机制

### 5.1 Controller 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| JSON格式无效 | 警告并要求重新提供有效JSON |
| 上下文长度超限 | 终止并返回错误信息 |
| 达到最大步数 | 强制进入最终答案阶段 |

### 5.2 Executor 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 代码执行失败 | 捕获traceback，要求重写，最多重试2次 |
| 包含matplotlib/seaborn | 警告并禁止，要求提供文本结果 |
| 结果token过长 (>16384) | 继续处理（可能需要截断） |
| 达到最大重试次数 | 返回错误消息给Controller |

### 5.3 回溯与重试流程

```
发生错误时
    │
    ▼
┌─────────────────────────────────────┐
│ 1. 记录错误到历史对话               │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 2. 提供具体的错误反馈               │
│    - "Execution failed:\n{error}"   │
│    - "Please revise your code and retry." │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. 重新调用LLM生成修正版本          │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 4. 如果2次重试都失败                │
│    - 返回错误给Controller           │
│    - Controller可能调整策略         │
└─────────────────────────────────────┘
```

### 5.4 超时处理

整个任务有超时保护（默认600秒）：

```python
signal.signal(signal.SIGALRM, handler)
...
try: 
    signal.alarm(args.timeout)
    prediction, trajectory, prompt = agent.run(...)
    signal.alarm(0)
except TimeoutError:
    logger.error(f"Loop {i} exceeded the time limit and was skipped")
    continue
```

---

## 6. 实际运行示例

### 6.1 任务描述

```
"On March 4, 2021, within the time range of 14:30 to 15:00, a single failure was detected in the system. 
The exact time when the root cause occurred is unknown. 
Please identify the specific occurrence time of the root cause."
```

任务类型：**task_1**（仅需确定根因发生时间）

### 6.2 预期执行步骤 (按Controller规则)

**步骤1**: 了解可用数据
```
Analysis: None (第一步)
Instruction: "First, let's explore the available telemetry data for the Bank system on 2021-03-04. List all metric files available and show the first few rows to understand the data structure."
```

**步骤2**: 计算全局阈值
```
Analysis: "We can see the metric data structure. Now we need to calculate global thresholds for each component-KPI time series."
Instruction: "Calculate P95 global thresholds for each component's each KPI using the entire day's data (2021-03-04). Use metric_container.csv first."
```

**步骤3**: 提取故障时间段数据
```
Analysis: "Global thresholds have been calculated. Now let's filter the data within the failure duration (14:30-15:00)."
Instruction: "Filter the metric data for the time range 2021-03-04 14:30:00 to 2021-03-04 15:00:00. Apply the global thresholds calculated in the previous step."
```

**步骤4**: 异常检测
```
Analysis: "Now we have the filtered data. Let's detect anomalies that exceed the global thresholds."
Instruction: "Identify consecutive anomalies in the filtered data that exceed the global P95 thresholds. Filter out isolated noise spikes."
```

**步骤5**: 根因定位
```
Analysis: "We've identified faulty components. Let's find the root cause."
Instruction: "Locate the first occurrence time of the most significant fault. That's our root cause occurrence time."
```

**步骤6**: 输出最终答案
```
Analysis: "We have successfully identified the root cause occurrence time."
Completed: "True"
Instruction: "The root cause occurred at 2021-03-04 14:57:00 on component Mysql02 due to high memory usage."
```

### 6.3 最终答案格式

```json
{
    "1": {
        "root cause occurrence datetime": "2021-03-04 14:57:00"
    }
}
```

---

## 🎯 关键要点总结

1. **两阶段协作**：Controller推理，Executor写代码
2. **原子性指令**：每一步只做一件事，清晰明确
3. **全局优先**：先计算全局阈值，再过滤局部数据
4. **多层分析**：metric → trace → log，逐步收敛
5. **候选约束**：最终答案必须从预定义列表选择
6. **状态保持**：IPython Kernel保留变量，提高效率
7. **自我修正**：支持代码执行失败后的重试
8. **结果总结**：自动将代码输出总结为自然语言

这个系统完整模拟了真实DevOps工程师的故障诊断思维过程！
