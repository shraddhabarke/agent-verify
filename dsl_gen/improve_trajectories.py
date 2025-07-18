import os
import json
import re
import sys
import traceback


from fastmcp import Client
from mcp.types import TextContent, ImageContent
from termcolor import colored

from agent_verify.agent import Agent
from dsl_gen.utils import *
from dsl_gen.lib_gen import *
from webvoyager_env import WebVoyagerEnv


class ImproveTrajectory(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env = WebVoyagerEnv()

    
                
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
    "explanation": "Why this function should be called next",
    "function": "function_name",
    "args": {"arg1": "value1", "arg2": "value2"},
    "stop": false,
    old_trajectory_steps: [step1, step2, step3]
}
In the arguments do not say to pick the output of previous steps. Give the concrete arguments.
Set "stop": true when (1) the user goal is achieved and no more functions are needed. or (2) when user goal cannot be satisifed.
'''.replace('OLD_TOOL_DESCRIPTIONS', str(old_funcs)).replace('NEW_TOOL_DESCRIPTIONS', str(new_funcs))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f'Query: {goal}'},
            {"role": "user", "content": f'Old Trajectory: {trajectory}'},
        ]
        for i in range(len(new_history)):
            messages.append({'role': 'assistant', 'content': f'{new_history[i]}'})
        response = self.llm_client.complete(model=self.model_name,messages=messages,response_format="json_object")
        completion = response.choices[0].message.content.strip()
        completion = json.loads(completion)
        return completion
    
    def get_final_answer(self, user_message):
        system_prompt = """You are an AI assistant that helps extracting relevant information from a large document.
Given a user goal and a result given by a tool, extract only the part of the tool result that satisfies the user goal. Keep the response concise and relevant.
Set "goal_achieved": true when the user goal is achieved, otherwise false.

Respond with JSON in this format:
{
    "explanation": "why the answer satisfies user goal",
    "answer": "extracted answer that satisfies the user goal",
    "goal_achieved": <true or false>,
}
"""
        messages=[{"role": "system", "content": system_prompt},{"role": "user", "content": user_message},]
        response = self.llm_client.complete(model=self.model_name,messages=messages,response_format="json_object")
        completion = response.choices[0].message.content.strip()
        completion = json.loads(completion)
        return completion

    


    
async def improve_trajectory(task, mcp_server, old_funcs, new_funcs):
    goal = task['query'].strip()
    trajectory = task['traj']

    agent = ImproveTrajectory()
    history = []
    step = 1
    final_result = None

    MAX_STEPS = 10
    goal_achieved = False
    task_log = {}

    task_log['tools'] = old_funcs + new_funcs
    traj = []

    mcp_client = Client(mcp_server)

    async with mcp_client:

        while step < MAX_STEPS:
            llm_response = agent.improve_trajectory(goal, trajectory, history, old_funcs, new_funcs)
            if not llm_response or llm_response['stop']:
                # print("\nTask complete or LLM indicated to stop.")
                user_message = f"Goal: {goal}\nFinal tool response to extract from:\n {json.dumps(final_result, indent=2)}"     
                llm_response = agent.get_final_answer(user_message)           
                final_result = llm_response['answer']
                goal_achieved = llm_response['goal_achieved']
                explanation = llm_response['explanation']
                break
            
            func_name = llm_response['function']
            args = llm_response['args']
            explanation = llm_response['explanation']
            old_trajectory_steps = llm_response['old_trajectory_steps']
            
            result = await agent.env.call_mcp_tool(mcp_client, func_name, args)
            traj_step = {
                "step": step,
                "function": func_name,
                "args": args,
                "explanation": explanation,
                "result": result,
                "old_trajectory_steps": old_trajectory_steps
            }
            traj.append(traj_step)            
            final_result = result
            
            # Update history
            history.append({
                "step": step,
                "function": func_name,
                "args": args,
                "result": result
            })
            step += 1
            if 'error' in result or 'Error' in result:
                goal_achieved = False
                explanation = 'Error occured'
                final_result = None
                break

    task_log['traj'] = traj
    task_log['goal_achieved'] = goal_achieved
    task_log['explanation'] = explanation
    task_log['final_result'] = final_result
    task_log['steps_taken'] = step  

    return task_log



# def improve_trajectories(tasks, mcp_client, old_funcs, new_funcs, improved_logs_folder, chunk_size=5):
#     return asyncio.run(improve_trajectories_(tasks, mcp_client, old_funcs, new_funcs, improved_logs_folder, chunk_size))

def improve_trajectories(tasks, mcp_server, old_funcs, new_funcs):
    logs = {}
    for i in range(len(tasks)):
        id = tasks[i]['id']
        task_log = asyncio.run(improve_trajectory(tasks[i], mcp_server, old_funcs, new_funcs))
        logs[id] = task_log

    return logs



# async def improve_trajectories_(tasks, mcp_client, old_funcs, new_funcs, improved_logs_folder, chunk_size=5):
#     # mcp_client = Client(mcp_server)
    
#     task_count = chunk_size # how many tasks that match the filter to execute; put a large number if you want to execute all tasks
#     count = task_count

#     async with mcp_client:
#         for task in tasks:
#             if count <= 0:
#                 break
#             count -= 1

#             print(task['id'])
#             log_file = os.path.normpath(f"{improved_logs_folder}/log_{task['id']}.txt")


#             # if os.path.exists(log_file):
#             #     continue

#             sys.stdout = open(log_file, 'w', encoding='utf-8')  # Suppress stdout for cleaner output
#             user_input = task['query']
#             print(f"Executing task: {user_input}")
#             try:
#                 result = await improve_trajectory(task, mcp_client, old_funcs, new_funcs)
#             except Exception as e:
#                 traceback.print_exc()
#                 result = None
#                 continue
#             if result is None or isinstance(result, str) or 'final_result' not in result.keys():
#                 print(result, type(result))
#             print(f"\nFinal Result: {result['final_result']}")
#             print(f"\nSteps taken: {result['step']}, Goal Achieved: {result['goal_achieved']}")

#             print("\n" + "="*50 + "\n")
    
            
#             sys.stdout.close()  # Close the suppressed stdout
#             sys.stdout = sys.__stdout__  # Restore original stdout


def correct_function(task_id):
    old_logs_folder = "agent_verify/WebVoyager/logs"
    improved_logs_folder = "agent_verify/WebVoyager/improved_logs"
    
    old_logs_file = os.path.normpath(f"{old_logs_folder}/log_{task_id}.txt")
    improved_logs_file = os.path.normpath(f"{improved_logs_folder}/log_{task_id}.txt")

    with open(old_logs_file, 'r', encoding='utf-8') as f:
        old_logs = f.read()
    with open(improved_logs_file, 'r', encoding='utf-8') as f:
        improved_logs = f.read()
    
    correct_func_from_traj(old_logs, improved_logs, task_id)



def check_trajectory_old(trajectory, new_func_name):
    error_in_traj = 1
    error_in_func = 2 
    no_error = 3
    lines = trajectory.splitlines()
    func_called = False
    stop_called = False 
    final_answer_present = False
    for line in lines:
        if 'Final Result' in line and 'error' not in line and 'Error' not in line:
            final_answer_present = True
            return no_error
        if 'Task complete or LLM indicated to stop.' in line:
            stop_called = True
        if new_func_name in line:
            func_called = True
        if func_called and "Result" in line:
            if 'Result: []' in line or 'error' in line or 'Error' in line or '"text": "[]"' in line:
                return error_in_func
            else:
                func_called = False
    return no_error

def check_trajectory(trajectory, new_func_name):
    error_in_traj = 1
    error_in_func = 2 
    no_error = 3
    func_called = False
    stop_called = False 
    final_answer_present = False

    if trajectory['final_result'] == '[{"type": "text", "text": "[]"}]' :
        return error_in_func

    for step in trajectory['traj']:
        if step['function'] == new_func_name:
            if 'error' in step['result'] or 'Error' in step['result']:
                print(colored(step, 'yellow'))
                return error_in_func
    return no_error


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