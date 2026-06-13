cand = """## POSSIBLE ROOT CAUSE COMPONENTS:

(service level — all instances of the service are faulty)
- frontend
- frontend-proxy
- frontend-web
- checkout
- payment
- cart
- inventory
- product-catalog
- accounting
- shipping
- email
- recommendation
- currency
- ad
- fraud-detection
- image-provider
- quote
- load-generator
- flagd

(node level — the root cause is a specific Kubernetes node)
- The node names can be found in `topology.json` under entities with type `k8s.node`.

## POSSIBLE ROOT CAUSE REASONS:

- httpError5xx (HTTP 5xx server errors)
- rateLimiting (request rate limiting triggered)
- trafficSurge (abnormal traffic spike)
- trafficHotspot (uneven traffic distribution)
- threadExhaustion (thread pool exhaustion)
- memoryPressure (container/pod memory pressure)
- nodeMemoryOOM (node-level memory OOM)
- nodeCpuHigh (high node CPU usage)
- cpuFullLoad (CPU at full capacity)
- cpuDeadLoop (CPU dead loop / infinite loop)
- fullGC (JVM full garbage collection)
- slowSQL (slow database queries)
- dbNetworkLatency (database network latency)
- redisUnavailable (Redis connection failure)
- cacheBreakdown (cache stampede / breakdown)
- messageQueueBacklog (message queue backlog)
- diskIOHigh (high disk I/O)
- loadBalancerFailure (load balancer failure)
- replicaScaleDown (unexpected replica scale-down)
- podCrashLoop (pod crash loop)
- podRestartFlapping (pod restart flapping)
- podPendingUnschedulable (pod pending due to scheduling failure)
- nodeDown (node down)
- resourceLimitMisconfig (resource limit misconfiguration)
- networkPolicyIsolation (network policy blocking traffic)
- dnsResolutionFailure (DNS resolution failure)
- codeDefect (application code defect / exception)
- nullPointerException (NullPointerException)"""

schema = f"""## TELEMETRY DIRECTORY STRUCTURE:

- Each task's telemetry data is located at: `rca100/cases/<task_id>/`
  For example: `rca100/cases/t001/`

- **IMPORTANT**: The task directory path is provided at the beginning of each issue as `[Task directory: ...]`. Always use this exact path. Do NOT derive the directory from XML attributes (such as `trans_id`, `event_id`, etc.) in the prompt text — those are alert identifiers, not directory names.

- The directory contains the following files:
  - `task.json`        — task metadata (alert info, time window, prompt)
  - `metrics.parquet`  — unified long-format metrics
  - `logs.parquet`     — application logs (OTel/SLS)
  - `traces.parquet`   — distributed traces (OTel spans)
  - `events.parquet`   — Kubernetes events
  - `alerts.parquet`   — alert lifecycle events (CMS alert center)
  - `topology.json`    — per-task entity graph (services, pods, nodes, edges)

- All telemetry data is in **Parquet format**. Use `pd.read_parquet()` to load them.
- Use `json.load()` to read `task.json` and `topology.json`.

## DATA SCHEMA

### 1. metrics.parquet (long-format, unified)

| column | type | description |
|---|---|---|
| `time` | int64 | unix **microseconds** |
| `domain` | string | `apm` or `k8s` |
| `entity_set` | string | e.g. `apm.service.legacy`, `apm.operation`, `apm.instance`, `apm.metric.jvm`, `apm.metric.thread`, `k8s.node`, `k8s.deployment`, `k8s.namespace`, `k8s.cluster` |
| `entity_id` | string | unique entity identifier |
| `entity_name` | string | human-readable entity name |
| `metric` | string | metric name, e.g. `request_count`, `error_rate`, `error_count`, `node_cpu_usage_rate`, `node_memory_usage_rate`, `latency`, `slow`, `slow_count` |
| `value` | float | metric value |
| `metric_set_id` | string | source metric set id |
| `service` | string | service name tag |

Key metrics: `request_count`, `error_count`, `error_rate`, `latency`, `slow`, `slow_count`, `node_cpu_usage_rate`, `node_memory_usage_rate`, `node_disk_usage_rate`, `cpu`, `mem`, `workload`, `deployment_desired_replicas`, `deployment_ready_replicas`, `deployment_available_replicas`, `deployment_availability_rate`, `deployment_cpu_usage_total`, `deployment_memory_usage_total`.

To get service-level metrics, filter by `entity_set == 'apm.service.legacy'`.
To get operation-level metrics, filter by `entity_set == 'apm.operation'`.
To get node-level metrics, filter by `entity_set == 'k8s.node'`.
To get JVM metrics, filter by `entity_set == 'apm.metric.jvm'`.
To get deployment metrics, filter by `entity_set == 'k8s.deployment'`.
**Important**: The `time` and `value` columns may be loaded as string type. Always convert them to numeric before comparison or aggregation: `df['time'] = pd.to_numeric(df['time'], errors='coerce')` and `df['value'] = pd.to_numeric(df['value'], errors='coerce')`.

### 2. logs.parquet

Application logs collected via OTel/SLS.

| column | type | description |
|---|---|---|
| `content` | string | log message content |
| `_time_` | string/int | log timestamp |
| `_source_` | string | log source |
| `_container_ip_` | string | container IP |
| `_image_name_` | string | container image name |
| `_container_name_` | string | container name |
| `_pod_name_` | string | pod name |
| `_namespace_` | string | Kubernetes namespace |
| `_pod_uid_` | string | pod UID |
| `_node_name_` | string | node name |
| `_node_ip_` | string | node IP |

To search for error logs, filter `content` using string matching (e.g. `content.str.contains('error', case=False)`).

### 3. traces.parquet

Distributed trace spans (OpenTelemetry format).

| column | type | description |
|---|---|---|
| `traceId` | string | trace identifier |
| `spanId` | string | span identifier |
| `parentSpanId` | string | parent span identifier |
| `kind` | string | span kind (CLIENT, SERVER, etc.) |
| `spanName` | string | span/operation name |
| `startTime` | int64 | span start time (nanoseconds) |
| `endTime` | int64 | span end time (nanoseconds) |
| `duration` | int64 | span duration (nanoseconds) |
| `serviceName` | string | service that produced the span |
| `statusCode` | int/string | gRPC/HTTP status code |
| `statusMessage` | string | status message / error description |
| `resources` | string/dict | OTel resource attributes |
| `attributes` | string/dict | span attributes |
| `events` | string/list | span events (exceptions, logs) |

To find error traces, filter by `statusCode` != 0 or check `statusMessage` for error text.
To find slow traces, sort by `duration` descending.
**Important**: Some columns (e.g., `startTime`, `endTime`, `duration`, `statusCode`) may be loaded as string type. Always convert them to numeric before comparison: `df['startTime'] = pd.to_numeric(df['startTime'], errors='coerce')`.

### 4. events.parquet (Kubernetes events)

| column | type | description |
|---|---|---|
| `eventId` | string | JSON-encoded k8s Event payload (parse to get `reason`, `message`, `involvedObject`) |
| `hostname` | string | node hostname |
| `level` | string | event level |
| `pod_id` | string | pod identifier |
| `pod_name` | string | pod name |
| `clusterId` | string | cluster identifier |
| `clusterName` | string | cluster name |

### 5. alerts.parquet (CMS alert center, CloudEvents 1.0)

| column | type | description |
|---|---|---|
| `type` | string | event type |
| `subtype` | string | event subtype |
| `source` | string | event source |
| `time` | string | event time |
| `subject` | string | alert subject |
| `severity` | string | alert severity |
| `status` | string | alert status (OCCURRED, RESOLVED, etc.) |
| `data` | string/dict | alert payload data |
| `labels` | string/dict | alert labels |
| `annotations` | string/dict | alert annotations |

### 6. topology.json (per-task entity graph)

```json
{{
  "entities": [{{"id": "<hash>", "type": "apm.service|k8s.pod|k8s.node|...", "name": "...", "props": {{...}}}}],
  "edges": [{{"src": "<id>", "src_type": "...", "dst": "<id>", "dst_type": "...", "relation": "contains|hosts|calls|same_as"}}],
  "stats": {{"entities_total": <int>, "edges_total": <int>}}
}}
```

Entity types include: `apm.service`, `apm.operation`, `apm.instance`, `k8s.pod`, `k8s.node`, `k8s.deployment`, `k8s.namespace`, `k8s.cluster`, `k8s.service`, `apm.external.database`, `apm.external.http_client`, `apm.external.rpc_client`, `apm.external.message`.

Relation types: `contains` (parent-child ownership), `hosts` (k8s-to-apm mapping), `calls` (service-to-service / service-to-middleware).

Use topology to understand service dependencies and call chains. The `calls` relation is especially useful for tracing fault propagation.

{cand}

## CLARIFICATION OF TELEMETRY DATA:

1. This is an OpenTelemetry demo e-commerce microservice system deployed on Kubernetes (Alibaba Cloud ACK). The services communicate via gRPC and HTTP.

2. Each task corresponds to a single chaos-drill incident. The `task.json` contains the alert information, the time window of the incident, and a `prompt_text` with the user's diagnosis request.

3. To start analysis, first read `task.json` to understand the alert context, then load `topology.json` to understand the service dependency graph, then explore metrics/logs/traces within the alert time window.

4. Timestamp conventions:
   - `metrics.parquet`: `time` is unix **microseconds** (divide by 1,000,000 to get seconds)
   - `traces.parquet`: `startTime`/`endTime`/`duration` are in **nanoseconds** (divide by 1,000,000,000 to get seconds)
   - `logs.parquet`: `_time_` varies, check the actual values
   - `alerts.parquet`: `time` is ISO8601 string, `timestamp` may be unix seconds

5. Please use the UTC+8 time zone in all analysis steps since the system is deployed in China (cn-hongkong region).

6. The entity names in metrics (e.g., `entity_name` field) match the `name` field in `topology.json` entities. Use this to cross-reference between telemetry data and topology.

7. To identify the root cause, follow the alert entity -> check its metrics (error_rate, latency) -> trace the call chain via topology `edges` (relation=`calls`) -> check upstream/downstream services -> identify the origin of the fault.

8. The `task.json` contains the following key fields:
   - `alert_title`: the alert name (e.g., "checkout 错误次数告警")
   - `alert_window`: contains `start` and `end` ISO8601 timestamps — the time window of the incident
   - `alert_entity`: the entity that triggered the alert (`entity_name`, `entity_type`, `entity_domain`)
   - `prompt_text`: the user's diagnosis request, which may contain XML-like `<code>` tags wrapping alert metadata. The core request is typically "帮我分析下根因" (help me analyze the root cause).

9. The `prompt_text` contains XML-like `<code vibeops_object type="alert_event">` tags. Inside these tags, you can find:
   - `rule_name`: the alert rule name
   - `entity_name`: the entity that triggered the alert (e.g., `checkout::/oteldemo.CheckoutService/PlaceOrder`)
   - `entity_type`: the entity type (e.g., `apm.operation`)
   - `alert_time`: the alert trigger time in UTC+8

10. For root cause diagnosis, use this workflow:
    - Read `task.json` to understand the alert context and time window
    - Load `topology.json` to understand the service dependency graph
    - Use `metrics.parquet` to find anomalous services/nodes within the alert time window
    - Use `topology.json` edges (relation=`calls`) to trace fault propagation from downstream to upstream
    - Use `traces.parquet` to confirm which service is the root cause among multiple faulty services
    - Use `logs.parquet` and `events.parquet` for additional evidence
"""

summary = """Now, you have decided to finish your reasoning process. You should now provide the final answer to the issue. The candidates of possible root cause components and reasons are provided to you. The root cause components and reasons must be selected from the provided candidates.

{cand}

Recall the issue is: {objective}

Please first review your previous reasoning process to infer an exact answer of the issue. Then, summarize your final answer of the root causes using the following JSON format at the end of your response:

```json
{{
    "root_cause_entities": ["(one or more entity names selected from the possible root cause component list)"],
    "root_cause_types": ["(one or more fault type codes selected from the possible root cause reason list)"]
}}
```
(Please use "```json" and "```" tags to wrap the JSON object.)
Note that all entity names must be selected from the possible root cause component list, and all fault types must be selected from the possible root cause reason list. Do not reply 'unknown' or 'null' in the JSON. Be decisive to infer a possible answer based on your current observation."""
