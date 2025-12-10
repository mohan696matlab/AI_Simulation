"""
Simulation Recontextualization Workflow

This module implements a LangGraph workflow that adapts existing simulation scenarios
to new contexts while preserving JSON structure and internal links.
"""

import json
import os
import time
from typing import List
import copy

from dotenv import load_dotenv
from genson import SchemaBuilder
import json_repair
from jsonschema import validate, ValidationError
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from deepdiff import DeepDiff

# Configuration


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=GEMINI_API_KEY,
    thinking_budget=0
)

# Constants
MAX_RETRIES = 3
SIMULATION_KEYS_TO_EXTRACT = [
    'lessonInformation',
    'assessmentCriterion',
    'selectedAssessmentCriterion',
    'simulationName',
    'simulationFlow',
    'workplaceScenario',
    'industryAlignedActivities',
    'selectedIndustryAlignedActivities'
]



# State Definition


class State(TypedDict):
    """Workflow state containing all necessary data for simulation recontextualization."""
    
    # Input scenario information
    current_scenario_option: str
    new_scenario_option: str
    current_scenario_example_json: dict
    
    # Validation schema
    validation_schema: dict
    
    # Generated outputs
    generated_schema: str
    
    # Validation tracking
    evaluator_message: str
    num_retries: int
    
    # History tracking
    history_generator: List[str]
    history_evaluator: List[str]
    message_history: List[dict]
    
    # Timing metrics
    simulation_start_time: float
    simulation_end_time: float
    simulation_duration: float
    
    # Final status
    schema_fidelity: str
    locked_field_equality: str
    changed_fields: List[str]
    output_json: dict

# Initialize State

def create_initial_state(current_scenario: str, new_scenario: str, 
                        scenario_json: dict) -> dict:
    """
    Creates an initial state dictionary for the workflow.
    
    Args:
        current_scenario: Description of the current simulation scenario
        new_scenario: Description of the target scenario
        scenario_json: The complete simulation JSON to be recontextualized
        validation_schema: JSON schema for validation
        
    Returns:
        Dictionary with initialized state values
    """
    return {
        'current_scenario_option': current_scenario,
        'new_scenario_option': new_scenario,
        'current_scenario_example_json': scenario_json,
        'generated_schema': '',
        'evaluator_message': '',
        'num_retries': 0,
        'history_generator': [],
        'history_evaluator': [],
        'message_history': [],
        'simulation_start_time': 0.0,
        'simulation_end_time': 0.0,
        'simulation_duration': 0.0,
    }


# Agent Functions


def recontextualize_agent(state: State) -> dict:
    """
    First agent: Recontextualizes all simulation data except the simulationFlow section.
    
    Args:
        state: Current workflow state
        
    Returns:
        Dictionary with updated state values
    """
    print(
    f'=== Recontextualization Start ===\n'
    f'From Scenario: {state["current_scenario_option"]}\n'
    f'=================================\n'
    f'To Scenario: {state["new_scenario_option"]}\n'
    f'=================================\n'
)

    
    simulation_start_time = time.time()
    
    # Extract relevant keys from the simulation JSON
    simulation_json = _extract_simulation_subset(
        state['current_scenario_example_json'],
        SIMULATION_KEYS_TO_EXTRACT
    )
    
    builder = SchemaBuilder()
    builder.add_object(simulation_json)
    validation_schema = builder.to_schema()
    
    # Build the prompt
    prompt = _build_recontextualization_prompt(
        old_scenario=state['current_scenario_option'],
        new_scenario=state['new_scenario_option'],
        simulation_json=simulation_json
    )
    
    # Update message history and get response
    updated_history = state['message_history'] + [{"role": "user", "content": prompt}]
    response = model.invoke(updated_history)
    
    print(f"✓ Recontextualization completed in {time.time() - simulation_start_time:.2f} seconds")
    
    return {
        'validation_schema': validation_schema,
        'simulation_start_time': simulation_start_time,
        'message_history': updated_history + [{"role": "assistant", "content": response.content}],
        'generated_schema': response.content,
        'history_generator': state['history_generator'] + [response.content]
    }


def validate_json(state: State) -> dict:
    """
    Validates the generated JSON against the schema.
    
    Args:
        state: Current workflow state
        
    Returns:
        Dictionary with validation results and updated retry count
    """
    
    print("Validating JSON schema...")
    
    try:
        # Clean and parse the generated JSON
        cleaned_json_text = _remove_markdown_code_blocks(state['generated_schema'])
        generated_json = json_repair.loads(cleaned_json_text)
        
        # Validate against schema
        validate(instance=generated_json, schema=state['validation_schema'])
        
        print("✓ JSON Schema Validation OK")
        return {
            'evaluator_message': 'PASS',
            'history_evaluator': state['history_evaluator'] + ['PASS']
        }
        
    except ValidationError as e:
        print(f"✗ JSON Schema Validation FAILED: {e.message}")
        return {
            'num_retries': state['num_retries'] + 1,
            'evaluator_message': f"JSON Schema Validation FAILED: {e.message}",
            'history_evaluator': state['history_evaluator'] + [e.message]
        }
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON Parse Error: {str(e)}")
        return {
            'num_retries': state['num_retries'] + 1,
            'evaluator_message': f"JSON Parse Error: {str(e)}",
            'history_evaluator': state['history_evaluator'] + [str(e)]
        }


def json_format_correction_agent(state: State) -> dict:
    """
    Corrects JSON format issues based on validation feedback.
    
    Args:
        state: Current workflow state
        
    Returns:
        Dictionary with corrected schema and updated history
    """
    
    print(f"Retry number: {state['num_retries']} || Attempting JSON format correction...")
    
    retry_prompt = _build_correction_prompt(state['evaluator_message'])
    
    response = model.invoke(
        state['message_history'] + [{"role": "user", "content": retry_prompt}]
    )
    
    print(f'finished JSON format correction attempt')
    
    return {
        'message_history': state['message_history'] + [
            {"role": "user", "content": retry_prompt},
            {"role": "assistant", "content": response.content}
        ],
        'generated_schema': response.content,
        'history_generator': state['history_generator'] + [response.content]
    }



# Routing Functions


def route_after_validation(state: State) -> str:
    """
    Determines the next step based on validation results.
    
    Args:
        state: Current workflow state
        
    Returns:
        String indicating the next route: 'Pass', 'Fail', or 'Retry Limit Exceeded'
    """
    if state['evaluator_message'] == 'PASS':
        return 'Pass'
    elif state['num_retries'] >= MAX_RETRIES:
        print(f"✗ Maximum retries ({MAX_RETRIES}) exceeded")
        return 'Retry Limit Exceeded'
    else:
        print(f"↻ Retry {state['num_retries']}/{MAX_RETRIES}")
        return 'Fail'
    

# Aggregator Function


def aggregator_node(state:State):
    
    
    print(f"✓ Aggregator Node: Starting aggregation process")
    
    start_time = time.time()
    
    with open("problem_statement/POC_sim_D.json", "r") as f:
        data = json.load(f)

    recontextualized_json = copy.deepcopy(data)

    state['generated_schema'] = json_repair.loads(state['generated_schema'])

    for key, value in state['generated_schema'].items():
        recontextualized_json['topicWizardData'][key] = value
        
    recontextualized_json['topicWizardData']['selectedScenarioOption'] = state['new_scenario_option']


    try:
        diff = DeepDiff(
                            data,
                            recontextualized_json,
                            ignore_order=True,
                            report_repetition=True,
                            hasher=None  # prevents hashing
                        )

        simulation_end_time = time.time()
        simulation_duration = simulation_end_time - state['simulation_start_time']
    except Exception as e:
        diff={}
        print(f"✗ Aggregator Node: Error in DeepDiff. The Change Log Could not be generated. \n {str(e)}")

    builder = SchemaBuilder()
    builder.add_object(data)
    validation_schema = builder.to_schema()

    try:
        validate(instance=recontextualized_json, schema=validation_schema)
        schema_fidelity='PASS'
        print("JSON conforms to the schema:")
    except ValidationError as e:
        print("JSON does not conform to the schema:")
        print(e)
        schema_fidelity='FAIL'
        
    if recontextualized_json['topicWizardData']['scenarioOptions'] == data['topicWizardData']['scenarioOptions']: 
        locked_field_equality='PASS'
    else:
        locked_field_equality='FAIL'
        
    print(f"✓ Aggregator Node: Aggregation process completed in {time.time() - start_time:.2f} seconds")
    
    print(f"✓ Aggregator Node: Schema Fidelity: {schema_fidelity}")
    print(f"✓ Aggregator Node: Locked Field Equality: {locked_field_equality}")
    print(f"✓ Aggregator Node: Simulation Duration: {simulation_duration:.2f} seconds")
    


    return {
        'schema_fidelity':schema_fidelity,
        'locked_field_equality':locked_field_equality,
        'output_json': recontextualized_json,
        'simulation_end_time': simulation_end_time,
        'simulation_duration': simulation_duration,
        'changed_fields': diff
    }




# Helper Functions


def _extract_simulation_subset(full_json: dict, keys_to_extract: List[str]) -> dict:
    """
    Extracts a subset of keys from the simulation JSON.
    
    Args:
        full_json: Complete simulation JSON
        keys_to_extract: List of keys to extract
        
    Returns:
        Dictionary containing only the specified keys
    """
    topic_wizard_data = full_json.get('topicWizardData', {})
    return {k: v for k, v in topic_wizard_data.items() if k in keys_to_extract}


def _remove_markdown_code_blocks(text: str) -> str:
    """
    Removes markdown code block markers from text.
    
    Args:
        text: Text potentially containing markdown code blocks
        
    Returns:
        Cleaned text without code block markers
    """
    text = text.strip()
    
    if text.startswith('```'):
        first_newline = text.find('\n')
        last_backticks = text.rfind('```')
        
        if first_newline != -1 and last_backticks != -1:
            return text[first_newline + 1:last_backticks].strip()
    
    return text


def _build_recontextualization_prompt(old_scenario: str, new_scenario: str, simulation_json: dict) -> str:
    """Builds the prompt for the initial recontextualization."""
    return f'''You are an expert simulation designer. Your task is to adapt an existing simulation (given as JSON) to a new scenario while preserving its structure and links.

Here is the current simulation scenario:
OLD SCENARIO: {old_scenario}

Simulation JSON (do not modify the structure or fields):
SIMULATION: {json.dumps(simulation_json, indent=2)}

Your objective:
- Re-contextualize all narrative, descriptions, and scenario-dependent content so that it aligns with the NEW SCENARIO:
NEW SCENARIO: {new_scenario}

Constraints:
1. Do not modify the JSON structure, keys, or data types.
2. Locked fields (everything not scenario-dependent) must remain identical.
3. Only adapt scenario-relevant content such as names, roles, narrative, instructions, examples, and context.
4. Ensure global coherence: the adapted simulation should read naturally, reflect the new scenario consistently, and contain no residual references to the old scenario.
5. Preserve formatting, arrays, objects, and any schema constraints.

Deliverable:
- Output ONLY the valid JSON object. Do not include any markdown formatting, code blocks, explanations, or additional text.
- Do not wrap the JSON in ```json or ``` markers.
- Return only the raw JSON that can be directly parsed.'''


def _build_correction_prompt(error_message: str) -> str:
    """Builds the prompt for JSON correction after validation failure."""
    return f'''The previous output did not satisfy the required JSON Schema.
A validation failure occurred with the following message:

{error_message}

You must correct all issues identified by the validator and produce a fully compliant JSON object.
Carefully review the schema constraints, adjust any incorrect fields or structural inconsistencies, and ensure that:

1. Every key strictly adheres to the expected schema.
2. All value types match the schema requirements.
3. No additional or missing fields exist.
4. Arrays and nested objects follow the exact structure defined by the schema.
5. The JSON remains syntactically valid and properly formatted.

After making the necessary corrections, re-generate the complete JSON output that fully conforms to the schema.
Provide only the corrected JSON in your response.'''




# Workflow Construction


def build_workflow(checkpoints=None) -> StateGraph:
    """
    Constructs and returns the complete LangGraph workflow.
    
    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(State)
    
    # Add nodes
    workflow.add_node("validate_json", validate_json)
    workflow.add_node("json_format_correction", json_format_correction_agent)
    workflow.add_node("recontextualize_agent", 
                     recontextualize_agent)
    workflow.add_node("aggregator_node",aggregator_node)
    
    # Define edges
    workflow.add_edge(START, "recontextualize_agent")
    workflow.add_edge("recontextualize_agent", "validate_json")
    
    # Conditional routing after validation
    workflow.add_conditional_edges(
        "validate_json",
        route_after_validation,
        {
            "Fail": "json_format_correction",
            "Pass": "aggregator_node",
            "Retry Limit Exceeded": END
        }
    )
    
    workflow.add_edge("json_format_correction", "validate_json")
    workflow.add_edge("aggregator_node", END)
    
    if checkpoints:
        graph = workflow.compile(checkpointer=checkpoints)
    else:
        graph = workflow.compile()
    
    return graph



# Main Execution



# Build and compile the workflow
# chain = build_workflow()
