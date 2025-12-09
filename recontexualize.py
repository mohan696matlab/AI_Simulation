import argparse
import json
import os
from langgraph.checkpoint.memory import InMemorySaver

from utlis import build_workflow, create_initial_state


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)


def run_cli(input_json, current_scenario, new_scenario, result_dir):

    print("Initializing state...")

    data = load_json(input_json)

    checkpointer = InMemorySaver()
    chain = build_workflow(checkpoints=checkpointer)

    state = create_initial_state(
        current_scenario=current_scenario,
        new_scenario=new_scenario,
        scenario_json=data
    )

    thread_config = {"configurable": {"thread_id": "1"}}

    try:
        result_state = chain.invoke(state, thread_config)
    except Exception as e:
        print(f"Error: {e}")
        print("The state is saved in:", f"{result_dir}/state.json")
        temp_state = list(chain.get_state_history(thread_config))[0].value
        save_json(f"{result_dir}/state.json", temp_state)
        return

    save_json(f"{result_dir}/output.json", result_state["output_json"])
    save_json(f"{result_dir}/changed_fields.json", result_state["changed_fields"])

    print("Processing complete.")
    print(f"Results saved in {result_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Run the scenario processing pipeline."
    )

    parser.add_argument(
        "--input_json",
        type=str,
        required=True,
        default='problem_statement/POC_sim_D.json',
        help="Path to the scenario JSON file."
    )

    parser.add_argument(
        "--current_scenario",
        type=str,
        default='''A strategy team at HarvestBowls is facing a drop in foot traffic after Nature\'s Crust introduced a $1 value menu. As a business consultant, learners must analyze the market shake-up, assess possible strategic responses,and recommend a plan that helps HarvestBowls maintain its loyal customer base, safeguard profitability, and uphold its commitment to serving fresh, organic, and wholesome fast food.''',
        required=True,
        help="Current scenario description string."
    )

    parser.add_argument(
        "--new_scenario",
        type=str,
        default='''FlexFit Gym memberships decline after rival BodyWorks introduces steeply discounted annual packages. Learners must recommend whether FlexFit should compete on price, expand digital offerings, or reinforce its premium brand.''',
        required=True,
        help="New scenario description string."
    )

    parser.add_argument(
        "--output_dir",
        type=str,
        default="results",
        help="Directory where results will be saved."
    )

    args = parser.parse_args()

    run_cli(
        input_json=args.input_json,
        current_scenario=args.current_scenario,
        new_scenario=args.new_scenario,
        result_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
'''
python recontexualize.py \
  --input_json problem_statement/POC_sim_D.json \
  --current_scenario "A strategy team at HarvestBowls is facing a drop..." \
  --new_scenario "FlexFit Gym memberships decline after rival BodyWorks..." \
  --output_dir results
'''
