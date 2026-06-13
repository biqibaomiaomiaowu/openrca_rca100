#!/usr/bin/env python3
"""
RCA100 全量并行测试脚本
3 个进程，每个跑 ~34 个任务，每个任务跑 3 次
"""
import subprocess
import os
import sys
import csv
import time

PROJECT_DIR = "/home/suiyicheng/RCAFolder/OpenRCA_rca100"
PYTHON = sys.executable  # 使用当前 conda 环境的 python

# 配置
BATCHES = [
    {"tag": "batch1", "start": 0,  "end": 33,  "desc": "t001-t034"},
    {"tag": "batch2", "start": 34, "end": 67,  "desc": "t035-t068"},
    {"tag": "batch3", "start": 68, "end": 102, "desc": "t069-t103"},
]
SAMPLE_NUM = 3
TIMEOUT = 900
MAX_STEP = 25


def launch_batch(batch):
    """启动一个批次的子进程"""
    cmd = [
        PYTHON, "rca/run_agent_standard.py",
        "--dataset", "rca100",
        "--start_idx", str(batch["start"]),
        "--end_idx", str(batch["end"]),
        "--sample_num", str(SAMPLE_NUM),
        "--timeout", str(TIMEOUT),
        "--controller_max_step", str(MAX_STEP),
        "--tag", batch["tag"],
    ]
    log_file = os.path.join(PROJECT_DIR, f"rca100_{batch['tag']}.log")
    log_fh = open(log_file, "w")
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        cwd=PROJECT_DIR,
    )
    return proc, log_fh, log_file


def merge_results():
    """合并 3 个批次的 CSV 结果"""
    csv_dir = os.path.join(PROJECT_DIR, "test/result/rca100")
    output = os.path.join(csv_dir, "agent-all.csv")
    batch_files = [
        os.path.join(csv_dir, f"agent-{b['tag']}-gpt-4o.csv")
        for b in BATCHES
    ]

    # 找第一个有内容的文件取 header
    header = None
    for f in batch_files:
        if os.path.exists(f):
            with open(f) as fh:
                reader = csv.reader(fh)
                header = next(reader)
                break
    if not header:
        print("❌ 没有找到任何结果文件")
        return

    all_rows = []
    for f in batch_files:
        if not os.path.exists(f):
            continue
        with open(f) as fh:
            reader = csv.reader(fh)
            next(reader)  # skip header
            for row in reader:
                all_rows.append(row)

    with open(output, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(all_rows)

    print(f"📊 合并完成: {output} ({len(all_rows)} 行)")
    return output


def print_stats(csv_path):
    """打印统计结果"""
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    scores = []
    for r in rows:
        try:
            scores.append(float(r["score"]))
        except (ValueError, KeyError):
            pass

    if not scores:
        print("  无有效分数")
        return

    print(f"  总样本数: {len(scores)}")
    # 按 task_index 去重统计
    tasks = {}
    for r in rows:
        tid = r.get("task_index", "")
        try:
            s = float(r["score"])
            if tid not in tasks or s > tasks[tid]:
                tasks[tid] = s
        except (ValueError, KeyError):
            pass

    task_scores = list(tasks.values())
    print(f"  独立任务数: {len(task_scores)}")
    print(f"  平均分 (去重): {sum(task_scores)/len(task_scores):.3f}")
    print(f"  满分 (1.0): {sum(1 for s in task_scores if s == 1.0)}")
    print(f"  半对 (0.5): {sum(1 for s in task_scores if s == 0.5)}")
    print(f"  全错 (0.0): {sum(1 for s in task_scores if s == 0.0)}")


def main():
    os.chdir(PROJECT_DIR)
    print("🚀 启动 3 个并行进程...")
    print(f"   Python: {PYTHON}")
    print(f"   每任务跑 {SAMPLE_NUM} 次，超时 {TIMEOUT}s，最大轮次 {MAX_STEP}")
    print()

    procs = []
    for b in BATCHES:
        proc, log_fh, log_file = launch_batch(b)
        procs.append((proc, log_fh, b))
        print(f"  {b['desc']} (idx {b['start']}-{b['end']}): PID={proc.pid}, log={log_file}")

    print(f"\n⏳ 等待全部完成...")
    print(f"   查看进度: tail -f rca100_batch*.log")
    print()

    start_time = time.time()

    # 等待所有进程完成
    for proc, log_fh, batch in procs:
        proc.wait()
        log_fh.close()
        elapsed = time.time() - start_time
        status = "✅" if proc.returncode == 0 else f"❌ (exit {proc.returncode})"
        print(f"  {batch['desc']} {status}  ({elapsed/60:.1f} min)")

    total_time = time.time() - start_time
    print(f"\n✅ 全部完成! 总耗时: {total_time/60:.1f} 分钟")

    # 合并结果
    print()
    csv_path = merge_results()

    # 统计
    if csv_path:
        print()
        print("📈 结果统计:")
        print_stats(csv_path)


if __name__ == "__main__":
    main()
