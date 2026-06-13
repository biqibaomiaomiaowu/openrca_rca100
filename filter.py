import csv
import os

# 配置路径
source_file = "/home/suiyicheng/RCAFolder/OpenRCA/test/result/Bank/agent-rca-gpt-4o.csv"
output_file = os.path.join(os.path.dirname(source_file), "agent-rca-gpt-4o-score-0.csv")

def is_score_zero(score_str):
    """判断score是否为0，兼容各种格式"""
    try:
        score = float(score_str.strip())
        return abs(score - 0.0) < 1e-9
    except (ValueError, AttributeError):
        return False

# 读取源文件并筛选
matched_rows = []
with open(source_file, 'r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames
    for row in reader:
        try:
            if is_score_zero(row.get('score', '')):
                matched_rows.append(row)
        except Exception:
            # 跳过格式错误的行
            continue

# 写入输出文件
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(matched_rows)

# 打印结果
print(f"✅ 筛选完成，共匹配到 {len(matched_rows)} 条score=0的记录")
print(f"✅ 结果已保存到：{output_file}")