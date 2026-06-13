#!/bin/bash
# RCA100 全量并行测试脚本
# 3 个进程，每个跑 ~34 个任务，每个任务跑 3 次

cd /home/suiyicheng/RCAFolder/OpenRCA_rca100

echo "🚀 启动 3 个并行进程..."

# 进程 1: t001 ~ t034 (idx 0-33)
nohup python rca/run_agent_standard.py \
  --dataset rca100 \
  --start_idx 0 \
  --end_idx 33 \
  --sample_num 3 \
  --timeout 900 \
  --tag batch1 \
  > rca100_batch1.log 2>&1 &
PID1=$!
echo "  Batch1 (t001-t034): PID=$PID1"

# 进程 2: t035 ~ t068 (idx 34-67)
nohup python rca/run_agent_standard.py \
  --dataset rca100 \
  --start_idx 34 \
  --end_idx 67 \
  --sample_num 3 \
  --timeout 900 \
  --tag batch2 \
  > rca100_batch2.log 2>&1 &
PID2=$!
echo "  Batch2 (t035-t068): PID=$PID2"

# 进程 3: t069 ~ t103 (idx 68-102)
nohup python rca/run_agent_standard.py \
  --dataset rca100 \
  --start_idx 68 \
  --end_idx 102 \
  --sample_num 3 \
  --timeout 900 \
  --tag batch3 \
  > rca100_batch3.log 2>&1 &
PID3=$!
echo "  Batch3 (t069-t103): PID=$PID3"

echo ""
echo "✅ 已启动，PID: $PID1 $PID2 $PID3"
echo ""
echo "查看进度："
echo "  tail -f rca100_batch1.log"
echo "  tail -f rca100_batch2.log"
echo "  tail -f rca100_batch3.log"
echo ""
echo "检查进程状态："
echo "  ps aux | grep run_agent_standard"
echo ""
echo "等待全部完成后，合并结果："
echo "  head -1 test/result/rca100/agent-batch1-gpt-4o.csv > test/result/rca100/agent-all.csv"
echo "  tail -n +2 test/result/rca100/agent-batch*.csv >> test/result/rca100/agent-all.csv"
echo ""

# 等待所有进程完成
echo "⏳ 等待所有进程完成..."
wait $PID1 $PID2 $PID3
echo "✅ 全部完成！"

# 合并结果
echo "📊 合并结果..."
head -1 test/result/rca100/agent-batch1-gpt-4o.csv > test/result/rca100/agent-all.csv
tail -n +2 test/result/rca100/agent-batch*.csv >> test/result/rca100/agent-all.csv

# 统计
echo ""
echo "📈 结果统计："
python3 -c "
import csv
with open('test/result/rca100/agent-all.csv') as f:
    rows = list(csv.DictReader(f))
scores = [float(r['score']) for r in rows if r['score'] != 'N/A']
print(f'  总任务数: {len(rows)}')
print(f'  平均分: {sum(scores)/len(scores):.3f}' if scores else '  无有效分数')
print(f'  满分 (1.0): {sum(1 for s in scores if s == 1.0)}')
print(f'  半对 (0.5): {sum(1 for s in scores if s == 0.5)}')
print(f'  全错 (0.0): {sum(1 for s in scores if s == 0.0)}')
"
