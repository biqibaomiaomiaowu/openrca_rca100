import pandas as pd
import os

# 任务描述映射
task_desc = {
    'task_1': '只需要确定根本原因发生时间',
    'task_2': '只需要确定根本原因',
    'task_3': '只需要确定根本原因组件',
    'task_4': '需要确定根本原因发生时间和原因',
    'task_5': '需要确定根本原因发生时间和组件',
    'task_6': '需要确定根本原因组件和原因',
    'task_7': '需要确定根本原因发生时间、组件和原因'
}

# 待处理的数据集配置
datasets = [
    {'file': '/home/suiyicheng/RCAFolder/OpenRCA/rca/archive/agent-Bank.csv', 'name': 'Bank'},
    {'file': '/home/suiyicheng/RCAFolder/OpenRCA/rca/archive/agent-Market-cloudbed-1.csv', 'name': 'Market-cloudbed-1'},
    {'file': '/home/suiyicheng/RCAFolder/OpenRCA/rca/archive/agent-Market-cloudbed-2.csv', 'name': 'Market-cloudbed-2'},
    {'file': '/home/suiyicheng/RCAFolder/OpenRCA/rca/archive/agent-Telecom.csv', 'name': 'Telecom'},
]

# 初始化统计结果
stats = {task: {
    'total': 0,
    'correct': 0,
    **{ds['name']: {'total': 0, 'correct': 0} for ds in datasets}
} for task in task_desc.keys()}

# 遍历所有数据集统计
for ds in datasets:
    if not os.path.exists(ds['file']):
        print(f"警告：文件 {ds['file']} 不存在，跳过")
        continue
    
    df = pd.read_csv(ds['file'])
    
    for task in task_desc.keys():
        task_data = df[df['task_index'] == task]
        task_total = len(task_data)
        task_correct = len(task_data[task_data['score'] == 1.0])
        
        stats[task]['total'] += task_total
        stats[task]['correct'] += task_correct
        stats[task][ds['name']]['total'] = task_total
        stats[task][ds['name']]['correct'] = task_correct

# 计算总和
total_all = sum(stats[task]['total'] for task in task_desc.keys())

# 生成输出数据
output_rows = []
for task in sorted(task_desc.keys(), key=lambda x: int(x.split('_')[1])):
    row = {
        '任务类型': task,
        '任务描述': task_desc[task],
        '总数': stats[task]['total'],
        '总数占比': f"{stats[task]['total']/total_all:.2%}" if total_all > 0 else "0.00%",
        '总成功率': f"{stats[task]['correct']/stats[task]['total']:.2%}" if stats[task]['total'] > 0 else "0.00%"
    }
    
    for ds in datasets:
        ds_name = ds['name']
        ds_total = stats[task][ds_name]['total']
        ds_correct = stats[task][ds_name]['correct']
        row[f'{ds_name}数量'] = ds_total
        row[f'{ds_name}占比'] = f"{ds_total/stats[task]['total']:.2%}" if stats[task]['total'] > 0 else "0.00%"
        row[f'{ds_name}成功率'] = f"{ds_correct/ds_total:.2%}" if ds_total > 0 else "0.00%"
    
    output_rows.append(row)

# 转换为DataFrame并保存
output_df = pd.DataFrame(output_rows)
output_path = '/home/suiyicheng/RCAFolder/OpenRCA/task_success_stats.csv'
output_df.to_csv(output_path, index=False, encoding='utf-8-sig')

print(f"统计完成！结果已保存到：{output_path}")
print("\n统计结果预览：")
print(output_df.to_string(index=False))