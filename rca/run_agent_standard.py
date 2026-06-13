import os
import sys
import json
import argparse
from tqdm import tqdm
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
from main.evaluate import evaluate, evaluate_rca100
from rca.api_router import configs

from datetime import datetime
from loguru import logger
from nbformat import v4 as nbf
import pandas as pd
import signal

# 让loguru的日志输出不打断tqdm进度条
logger.remove()
logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True, enqueue=True, level="INFO")

def handler(signum, frame):
    raise TimeoutError("Loop execution exceeded the time limit")

def main(args, uid, dataset):

    from rca.baseline.rca_agent.rca_agent import RCA_Agent
    import rca.baseline.rca_agent.prompt.agent_prompt as ap
    if dataset == "Telecom":
        import rca.baseline.rca_agent.prompt.basic_prompt_Telecom as bp
    elif dataset == "Bank":
        import rca.baseline.rca_agent.prompt.basic_prompt_Bank as bp
    elif dataset == "Market/cloudbed-1" or dataset == "Market/cloudbed-2":
        import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp
    elif dataset == "rca100":
        import rca.baseline.rca_agent.prompt.basic_prompt_rca100 as bp

    eval_file = f"test/result/{dataset}/agent-{args.tag}-{configs['MODEL'].split('/')[-1]}.csv"
    obs_path = f"test/monitor/{dataset}/agent-{args.tag}-{configs['MODEL'].split('/')[-1]}"
    unique_obs_path = f"{obs_path}/{uid}"

    if dataset == "rca100":
        # RCA100: build task list from per-case task.json files
        cases_dir = "rca100/cases"
        if not os.path.isdir(cases_dir):
            raise FileNotFoundError(f"Please download the RCA100 dataset first. Expected: {cases_dir}/")
        task_rows = []
        task_dirs = sorted([d for d in os.listdir(cases_dir) if os.path.isdir(os.path.join(cases_dir, d)) and d.startswith('t')])
        for tid in task_dirs:
            task_json_path = os.path.join(cases_dir, tid, "task.json")
            if os.path.exists(task_json_path):
                with open(task_json_path, 'r', encoding='utf-8') as f:
                    tdata = json.load(f)
                task_rows.append({
                    "task_index": tdata.get("task_id", tid),
                    "instruction": tdata.get("prompt_text", ""),
                    "scoring_points": "",  # RCA100 has no scoring_points
                    "task_id_str": tid,
                })
        instruct_data = pd.DataFrame(task_rows)
        # RCA100: load ground truth from answer_key directory
        gt_dir = "rca100/answer_key"
        gt_data = {}
        if os.path.isdir(gt_dir):
            for f in os.listdir(gt_dir):
                if f.endswith('.gt.json'):
                    tid = f.replace('.gt.json', '')
                    gt_data[tid] = os.path.join(gt_dir, f)
    else:
        inst_file = f"dataset/{dataset}/query.csv"
        gt_file = f"dataset/{dataset}/record.csv"
        if not os.path.exists(inst_file) or not os.path.exists(gt_file):
            raise FileNotFoundError(f"Please download the dataset first.")
        instruct_data = pd.read_csv(inst_file)
        gt_data = pd.read_csv(gt_file)

    if not os.path.exists(f"{unique_obs_path}/history"):
        os.makedirs(f"{unique_obs_path}/history")
    if not os.path.exists(f"{unique_obs_path}/trajectory"):
        os.makedirs(f"{unique_obs_path}/trajectory")
    if not os.path.exists(f"{unique_obs_path}/prompt"):
        os.makedirs(f"{unique_obs_path}/prompt")
    if not os.path.exists(eval_file):
        if not os.path.exists(f"test/result/{dataset}"):
            os.makedirs(f"test/result/{dataset}")
        eval_df = pd.DataFrame(columns=["instruction", "prediction", "groundtruth", "passed", "failed", "score"])
    else:
        eval_df = pd.read_csv(eval_file)

    scores = {
        "total": 0,
        "easy": 0,
        "middle": 0,
        "hard": 0,
        "rca100": 0,
    }
    nums = {
        "total": 0,
        "easy": 0,
        "middle": 0,
        "hard": 0,
        "rca100": 0,
    }

    signal.signal(signal.SIGALRM, handler)
    # logger.info(f"Using dataset: {dataset}")
    # logger.info(f"Using model: {configs['MODEL'].split('/')[-1]}")
    
    # for idx, row in instruct_data.iterrows():

    #     if idx < args.start_idx:
    #             continue
    #     if idx > args.end_idx:
    #         break
    logger.info(f"Using dataset: {dataset}")
    logger.info(f"Using model: {configs['MODEL'].split('/')[-1]}")

    # 计算任务范围
    start = args.start_idx
    end = args.end_idx if args.end_idx is not None else len(instruct_data) - 1
    total_tasks = end - start + 1
    logger.info(f"本次运行任务总数：{total_tasks} 个，行号范围：{start} ~ {end}")

        # 初始化tqdm进度条
    pbar = tqdm(
        total=total_tasks,
        desc="🔍 RCA根因分析进度",
        unit="个任务",
        colour="#2ecc71",
        bar_format="{l_bar}{bar:20}{r_bar}",
        dynamic_ncols=True
    )

    for idx, row in instruct_data.iterrows():
        if idx < start:
            continue
        if idx > end:
            break
    
        # 更新进度条，显示当前任务信息
        pbar.update(1)
        pbar.set_postfix(
            当前任务=row["task_index"],
            行号=idx,
            refresh=True
        )


        
        instruction = row["instruction"]
        task_index = row["task_index"]

        # RCA100: prepend task directory path to instruction so the agent knows where data lives
        if dataset == "rca100" and row.get("task_id_str"):
            task_dir = f"rca100/cases/{row['task_id_str']}"
            instruction = f"[Task directory: {task_dir}]\n{instruction}"
        scoring_points = row["scoring_points"] if pd.notna(row.get("scoring_points", None)) and row.get("scoring_points", "") != "" else None
        best_score = 0

        if dataset == "rca100":
            # RCA100: task_index is like "t001", no easy/middle/hard catalog
            task_num = int(task_index.replace('t', ''))
            catalog = "rca100"
        else:
            task_num = int(task_index.split('_')[1])
            if task_num <= 3:
                catalog = "easy"
            elif task_num <= 6:
                catalog = "middle"
            elif task_num <= 7:
                catalog = "hard"

        for i in range(args.sample_num):
            uuid = uid + f"_#{idx}-{i}"
            nb = nbf.new_notebook()
            nbfile = f"{unique_obs_path}/trajectory/{uuid}.ipynb"
            promptfile = f"{unique_obs_path}/prompt/{uuid}.json"
            logfile = f"{unique_obs_path}/history/{uuid}.log"
            logger.remove()
            logger.add(sys.stdout, colorize=True, enqueue=True, level="INFO")
            logger.add(logfile, colorize=True, enqueue=True, level="INFO")
            logger.debug('\n' + "#"*80 + f"\n{uuid}: {task_index}\n" + "#"*80)
            try: 
                signal.alarm(args.timeout)

                agent = RCA_Agent(ap, bp)
                prediction, trajectory, prompt = agent.run(instruction, 
                                                       logger, 
                                                       max_step=args.controller_max_step, 
                                                       max_turn=args.controller_max_turn)
                
                signal.alarm(0)

                for step in trajectory:
                    code_cell = nbf.new_code_cell(step['code'])
                    result_cell = nbf.new_markdown_cell(f"```\n{step['result']}\n```")
                    nb.cells.append(code_cell)
                    nb.cells.append(result_cell)
                with open(nbfile, 'w', encoding='utf-8') as f:
                    json.dump(nb, f, ensure_ascii=False, indent=4)
                logger.info(f"Trajectory has been saved to {nbfile}")

                with open(promptfile, 'w', encoding='utf-8') as f:
                    json.dump({"messages": prompt}, f, ensure_ascii=False, indent=4)
                logger.info(f"Prompt has been saved to {promptfile}")

                # Build ground truth string and evaluate
                if dataset == "rca100":
                    # RCA100 evaluation
                    tid = row.get("task_id_str", task_index)
                    gt_path = gt_data.get(tid) if isinstance(gt_data, dict) else None
                    if gt_path:
                        with open(gt_path, 'r', encoding='utf-8') as f:
                            gt_json = json.load(f)
                        gt_str = json.dumps({k: gt_json[k] for k in ("root_cause_entities", "root_cause_types") if k in gt_json}, ensure_ascii=False)
                    else:
                        gt_str = "N/A"

                    new_eval_df = pd.DataFrame([{"row_id": idx,
                                                "task_index": task_index,
                                                "instruction": instruction,
                                                "prediction": prediction,
                                                "groundtruth": gt_str,
                                                "passed": "N/A",
                                                "failed": "N/A",
                                                "score": "N/A"}])
                    eval_df = pd.concat([eval_df, new_eval_df],
                                        ignore_index=True)

                    if gt_path:
                        passed_criteria, failed_criteria, score = evaluate_rca100(prediction, gt_path)
                        logger.info(f"Prediction: {prediction}")
                        logger.info(f"Ground Truth: {gt_str}")
                        logger.info(f"Passed: {passed_criteria}")
                        logger.info(f"Failed: {failed_criteria}")
                        logger.info(f"Score: {score}")
                        best_score = max(best_score, score)

                        eval_df.loc[eval_df.index[-1], "passed"] = '\n'.join(passed_criteria)
                        eval_df.loc[eval_df.index[-1], "failed"] = '\n'.join(failed_criteria)
                        eval_df.loc[eval_df.index[-1], "score"] = score
                    else:
                        logger.info(f"Task {task_index} completed (no gt). Prediction: {prediction[:200]}...")

                    eval_df.to_csv(eval_file, index=False)

                elif gt_data is not None:
                    gt_str = '\n'.join([f'{col}: {gt_data.iloc[idx][col]}' for col in gt_data.columns if col != 'description'])

                    new_eval_df = pd.DataFrame([{"row_id": idx,
                                                "task_index": task_index,
                                                "instruction": instruction,
                                                "prediction": prediction,
                                                "groundtruth": gt_str,
                                                "passed": "N/A",
                                                "failed": "N/A",
                                                "score": "N/A"}])
                    eval_df = pd.concat([eval_df, new_eval_df],
                                        ignore_index=True)
                    eval_df.to_csv(eval_file,
                                   index=False)

                    if scoring_points:
                        passed_criteria, failed_criteria, score = evaluate(prediction, scoring_points)
                        logger.info(f"Prediction: {prediction}")
                        logger.info(f"Scoring Points: {scoring_points}")
                        logger.info(f"Passed Criteria: {passed_criteria}")
                        logger.info(f"Failed Criteria: {failed_criteria}")
                        logger.info(f"Score: {score}")
                        best_score = max(best_score, score)

                        eval_df.loc[eval_df.index[-1], "passed"] = '\n'.join(passed_criteria)
                        eval_df.loc[eval_df.index[-1], "failed"] = '\n'.join(failed_criteria)
                        eval_df.loc[eval_df.index[-1], "score"] = score
                        eval_df.to_csv(eval_file,
                                       index=False)
                    else:
                        logger.info(f"Task {task_index} completed. Prediction: {prediction[:200]}...")
                
                temp_scores = scores.copy()
                temp_scores[catalog] += best_score
                temp_scores["total"] += best_score
                temp_nums = nums.copy()
                temp_nums[catalog] += 1
                temp_nums["total"] += 1

            except TimeoutError:
                logger.error(f"Loop {i} exceeded the time limit and was skipped")
                continue
      
        scores = temp_scores
        nums = temp_nums
        # 全部跑完关闭进度条
    pbar.close()
    logger.info(f"✅ 所有 {total_tasks} 个任务运行完成！")

if __name__ == "__main__":
    
    uid = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="Market/cloudbed-1")
    parser.add_argument("--sample_num", type=int, default=1)
    parser.add_argument("--start_idx", type=int, default=0)
    parser.add_argument("--end_idx", type=int, default=150)
    parser.add_argument("--controller_max_step", type=int, default=25)
    parser.add_argument("--controller_max_turn", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--tag", type=str, default='rca')
    parser.add_argument("--auto", type=bool, default=False)

    args = parser.parse_args()

    if args.auto:
        print(f"Auto mode is on. Model is fixed to {configs['MODEL']}")
        datasets = ["Market/cloudbed-1", "Market/cloudbed-2", "Bank", "Telecom"]
        for dataset in datasets:
            main(args, uid, dataset)
    else:
        dataset = args.dataset
        main(args, uid, dataset)