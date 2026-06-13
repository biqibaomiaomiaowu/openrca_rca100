import csv
from collections import Counter

file_path = "/home/suiyicheng/RCAFolder/OpenRCA/test/result/Bank/agent-rca-gpt-4o.csv"

with open(file_path, 'r', encoding='utf-8', newline='') as f:
    reader = csv.reader(f)
    # 读取所有逻辑行
    all_logic_rows = list(reader)
    
    total_logic_rows = len(all_logic_rows)
    # 排除表头的逻辑行数
    data_logic_rows = total_logic_rows - 1 if total_logic_rows > 0 else 0
    
    # 统计有效数据行（排除全空的逻辑行）
    valid_data_rows = sum(1 for row in all_logic_rows[1:] if any(cell.strip() for cell in row))
    
    # 统计不同任务的数量（按task_index去重）
    task_indices = [row[-1].strip() for row in all_logic_rows[1:] if len(row) > 0 and row[-1].strip()]
    unique_task_count = len(Counter(task_indices))

print(f"✅ CSV总逻辑行数（包含表头）：{total_logic_rows}")
print(f"✅ 数据逻辑行数（排除表头）：{data_logic_rows}")
print(f"✅ 有效数据逻辑行数（排除表头+空行）：{valid_data_rows}")
print(f"✅ 唯一任务数量（去重task_index）：{unique_task_count}")