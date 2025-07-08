import os
import json
import re
import sys
import traceback

from termcolor import colored
from fastmcp import Client
from mcp.types import TextContent, ImageContent

from agent_verify.agent import Agent
from dsl_gen.utils import *

class ImproveTrajectory(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def fix_json_response(self, response: str) -> dict:
        """
        Fixes common JSON formatting issues in a string response.
        
        Args:
            response (str): The response string from ChatGPT.
            
        Returns:
            dict: The JSON-compatible dictionary.
        """
        # Attempt to parse the JSON without any modifications
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass  # If it fails, continue with the processing steps
        
        # Remove markdown JSON code fences and the `json` keyword
        response = re.sub(r'```json\n|```|json', '', response)
        
        # Replace non-standard quotes with standard double quotes
        response = response.replace('“', '"').replace('”', '"')
        
        # Replace invalid fractions with their approximate decimal equivalents
        response = re.sub(r'(\d+)/(\d+)', lambda m: str(float(m.group(1)) / float(m.group(2))), response)
        
        # Strip leading and trailing whitespace
        response = response.strip()
        
        # Attempt to find JSON object or array within the string
        match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', response)
        
        if match:
            cleaned_string = match.group(0)
        else:
            # If no JSON object or array is found, assume the whole response needs fixing
            cleaned_string = response
        
        # Count the number of opening and closing braces
        open_curly = cleaned_string.count('{')
        close_curly = cleaned_string.count('}')
        open_square = cleaned_string.count('[')
        close_square = cleaned_string.count(']')
        
        # Attempt to add enclosing brackets if missing
        if open_curly == 1 and close_curly == 0:
            cleaned_string += '}'
        elif close_curly == 1 and open_curly == 0:
            cleaned_string = '{' + cleaned_string
        elif open_square == 1 and close_square == 0:
            cleaned_string += ']'
        elif close_square == 1 and open_square == 0:
            cleaned_string = '[' + cleaned_string

        # Handle case where both opening and closing brackets are missing
        if open_curly == 0 and close_curly == 0 and open_square == 0 and close_square == 0:
            cleaned_string = '{' + cleaned_string + '}'
        
        # Attempt to fix common issues and parse the JSON
        try:
            return json.loads(cleaned_string)
        except json.JSONDecodeError:
            # Handle common issues
            cleaned_string = cleaned_string.replace("'", '"')  # Replace single quotes with double quotes
            cleaned_string = cleaned_string.replace("\n", " ")  # Remove newlines
            cleaned_string = cleaned_string.replace("\t", " ")  # Remove tabs

            try:
                return json.loads(cleaned_string)
            except json.JSONDecodeError:
                try:
                    wrapped_string = f"[{cleaned_string}]"
                    return json.loads(wrapped_string)
                except json.JSONDecodeError:
                    #raise ValueError("Unable to fix JSON response")
                    return cleaned_string
                
    def improve_trajectory(self, goal, trajectory, new_history, old_funcs, new_funcs):
        system_prompt = '''
You are an expert at improving the code. The user had to solve a task and was provided with some tools to do that.
The user generated a trajectory to solve the tasks using the functions.
But now we have expanded the library by including more functions.
You task is to identify the sequence of steps in the trajectory that can be potentially clubbed using the new functions now.
Output only the updated trajectory.
Here is a list of the old functions: OLD_TOOL_DESCRIPTIONS
Here is a list of the new functions: NEW_TOOL_DESCRIPTIONS
Your job is to generate a new trajectory that closely resembles the original trajectory. But make sure to generate one step at a time. 
Also, make sure to not choose any other recipes than what the old trajectory chose, ofcourse wherever possible.
We will execute the step and get you the result. Based on the result and the original trajectory, you will generate the next step.
You should also highlight, which steps in the old trajectory you are tyring to combine.
You will be ultimately judged on how many steps were you able to reduce compared to the old trajectory.
You win only if you are able to complete the same task with a smaller number of steps.
Respond with JSON in this format:
{
    "function": "function_name",
    "args": {"arg1": "value1", "arg2": "value2"},
    "stop": false,
    "explanation": "Why this function should be called next",
    old_trajectory_steps: [step1, step2, step3]
}

Set "stop": true when (1) the user goal is achieved and no more functions are needed. or (2) when user goal cannot be satisifed.
'''.replace('OLD_TOOL_DESCRIPTIONS', str(old_funcs)).replace('NEW_TOOL_DESCRIPTIONS', str(new_funcs))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f'Query: {goal}'},
            {"role": "user", "content": f'Old Trajectory: {trajectory}'},
        ]
        # print(colored(new_history, 'magenta'))
        for i in range(len(new_history)):
            messages.append({'role': 'assistant', 'content': f'{new_history[i]}'})
        response = self.llm_client.complete(
            model=self.model_name,
            messages=messages,
        )
        completion = response.choices[0].message.content.strip()
        return completion
    
    def get_final_answer(self, user_message):
        system_prompt = """You are an AI assistant that helps extracting relevant information from a large document.
Given a user goal and a result given by a tool, extract only the part of the tool result that satisfies the user goal. Keep the response concise and relevant.

Respond with JSON in this format:
{
    "answer": "extracted answer that satisfies the user goal",
    "goal_achieved": false,
    "explanation": "why the answer satisfies user goal",
}
Set "goal_achieved": true when the user goal is achieved, otherwise false.
"""
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return completion

    

    
    
async def call_mcp_tool(mcp_client:Client, function_name, function_args):
    """ Calls a function on the MCP server and returns the result."""
    try:
        async with mcp_client:
            resp_items = []
            print(f"Function Name: {function_name} Function Args: {function_args}")
            func_response = await mcp_client.call_tool(function_name, function_args)
            func_response = func_response.content
            for item in func_response:
                if isinstance(item, TextContent):
                    resp_items.append({"type": "text", "text": item.text})
                elif isinstance(item, ImageContent):
                    resp_items.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{item.mimeType};base64,{item.data}",
                        },
                    })
                else:
                    raise ValueError(f"Unsupported content type: {type(item)}")
        
    except Exception as e:
        traceback.print_exc()
        resp_items.append({"type": "text", "text": str(e)})
    return json.dumps(resp_items)

    
async def improve_trajectory(task, mcp_client, old_funcs, new_funcs):
    goal = task['query'].strip()
    trajectory = task['traj']

    agent = ImproveTrajectory()
    history = []
    step = 1
    final_result = None

    while True:
        response = agent.improve_trajectory(goal, trajectory, history, old_funcs, new_funcs)
        llm_response = agent.fix_json_response(response)
        if isinstance(llm_response, str):
            print(llm_response)
            return None
        if not llm_response or llm_response.get("stop"):
            print("\nTask complete or LLM indicated to stop.")
            user_message = f"Goal: {goal}\nFinal tool response to extract from:\n {json.dumps(final_result, indent=2)}"     
            response = agent.get_final_answer(user_message)           
            llm_response = agent.fix_json_response(response)
            final_result = llm_response.get("answer", None)
            goal_achieved = llm_response.get("goal_achieved", False)
            explanation = llm_response.get("explanation", "")
            break
        if llm_response.get("answer"):
            print(f"\nLLM provided an answer: {llm_response['answer']}")
            goal_achieved = llm_response.get("goal_achieved", False)
            result = llm_response['answer']
        else:
            func_name = llm_response.get("function")
            args = llm_response.get("args", {})
            explanation = llm_response.get("explanation", "")
            print(colored(f"\nStep {step}: LLM suggests calling '{func_name}' with args {args}", 'blue'))
            if explanation:
                print(f"Reason: {explanation}")

            old_trajectory_steps = llm_response.get("old_trajectory_steps", [])
            print(f"Old trajectory steps: {old_trajectory_steps}")
            
            result = await call_mcp_tool(mcp_client, func_name, args)
            print(colored(f"Result: {result}", 'green'))
        final_result = result
        
        # Update history
        history.append({
            "step": step,
            "function": func_name,
            "args": args,
            "result": result
        })
        step += 1

    return {
        "final_result": final_result,
        "step": step - 1,
        "goal_achieved": goal_achieved
        }


def improve_trajectories(tasks, mcp_client, old_funcs, new_funcs, improved_logs_folder):
    task_count = 100 # how many tasks that match the filter to execute; put a large number if you want to execute all tasks
    count = task_count
    for task in tasks:
        if count <= 0:
            break

        print(task['id'])
        log_file = os.path.normpath(f"{improved_logs_folder}/log_{task['id']}.txt")


        if os.path.exists(log_file):
            continue
        sys.stdout = open(log_file, 'w', encoding='utf-8')  # Suppress stdout for cleaner output
        user_input = task['query']
        print(f"Executing task: {user_input}")
        result = asyncio.run(improve_trajectory(task, mcp_client, old_funcs, new_funcs))
        print(f"\nFinal Result: {result['final_result']}")
        print(f"\nSteps taken: {result['step']}, Goal Achieved: {result['goal_achieved']}")

        print("\n" + "="*50 + "\n")
 
        count -= 1
        sys.stdout.close()  # Close the suppressed stdout
        sys.stdout = sys.__stdout__  # Restore original stdout



def main():
    ########## CONFIG ##########
    old_mcp_server = 'agent_verify/WebVoyager/AllRecipes.py'
    new_mcp_server = 'agent_verify/WebVoyager/AllRecipes_test.py'
    logs_folder = "agent_verify/WebVoyager/logs"
    improved_logs_folder = "agent_verify/WebVoyager/improved_logs"
    task_file = "agent_verify/WebVoyager/WebVoyager_data.jsonl"
    task_filter = "Allrecipes"

    ########## TOOLS AND TASKS##########
    old_funcs = get_tools(old_mcp_server)
    new_funcs = get_tools(new_mcp_server)
    tasks = get_tasks(logs_folder, task_file, task_filter)
    tasks = tasks[:5]
    client = Client(new_mcp_server)

    ########## IMPROVE TRAJECTORIES ##########
    improve_trajectories(tasks, client, old_funcs, new_funcs, improved_logs_folder)


if __name__ == "__main__":
    main()