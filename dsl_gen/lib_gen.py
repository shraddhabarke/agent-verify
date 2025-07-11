import os
import json
import asyncio
from fastmcp import Client
from termcolor import colored
from agent_verify.agent import Agent
from dsl_gen.utils import *



class FunctionSuggestionAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def suggest_funcs(self, tasks, library):
        system_prompt = f'''
You are an expert at generating functions from tasks.
You will be given a list of queries and the steps taken to solve them.
Your task is to propose high-level functions that are commonly used in solving these queries.
You are also given the current library of already defined functions.
You need to suggest one function that can be added to this library and can be used in most of the observed tasks.
Output only the name of the function, its arguments and the description in the following format:

Function Name: <name of the function>
Function Arguments: <arguments of the function>
Function Description: <description of the function>
'''
        user_message = "\n".join(f"Query: {task['query']}\nSteps: {task['traj']}" for task in tasks)
        user_message += f"\nCurrent Library: {library}"
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        completion = response.choices[0].message.content.strip()
        res = self.parse_result(completion)
        return res
    
    def parse_result(self, result):
        functions = []
        lines = result.splitlines()
        i = 0

        while i < len(lines):
            if lines[i].startswith("Function Name:"):
                name = lines[i].split("Function Name:")[1].strip()
                i += 1

                # Parse multi-line arguments
                args = []
                if i < len(lines) and lines[i].startswith("Function Arguments:"):
                    i += 1
                    while i < len(lines) and lines[i].strip().startswith("-"):
                        line = lines[i].strip().lstrip("-").strip()
                        if ":" in line:
                            arg_name, arg_type = [s.strip() for s in line.split(":", 1)]
                            args.append((arg_name, arg_type))
                        i += 1

                # Now get the description
                if i < len(lines) and lines[i].startswith("Function Description:"):
                    desc = lines[i].split("Function Description:")[1].strip()
                    i += 1
                else:
                    desc = ""

                functions.append({
                    "name": name,
                    "arguments": args,
                    "description": desc
                })
            else:
                i += 1

        return functions

    
class LibRankerAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def rank_funcs(self, funcs):
        system_prompt = f'''
You are an expert in creating a library of functions.
You will be given a list of functions that are are defined.
You are also given a list of functions that we wish to define. 
However, while defining a function, you may need the other one. 
So, your task is to rank the functions in such a way that to define a function with a lower rank we do not need the function with a higher rank.
So, basically give a topological sort.
Output in the following format:
function_1
function_2
...
Just output the function names in the correct order.       
Do not output any explanation or anything else. 
If there are multiple functions that can be defined, prefer the one that has more utility.
'''
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(funcs)},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return completion
    

class FuncDefinitionAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def define_func(self, library, new_func, tasks):
        system_prompt = f'''
You are an expert in writing new functions. 
You will be given a list of queries and the steps taken to solve them.
The user has a set of functions that can be used to solve the queries.
However, the user has suggested a new function that would be helpful to add to the current set.
Your task is to define the new function.
You can use the functions in the current set.
You can use the queries and the steps taken to solve them to understand what the function does.    
Do not use any function that is not in the current set.
Remember the all the inputs to the function must be string. You can typcast them internally if you want. 
For example, if you want an input parameter x to be a string, you should expect that the user will provide it as a string.
You can internally say x = str(x).
Regardless of the types, in the function definition, do not give any type hints.
Also, make sure that your function has a doc string.
Output a JSON object in the following fomat:
{{
    "new_function": <new_function>,
    "explanation": <explanation>
}}
'''
        user_message = f'Current available functions: {library}\nNew function: {new_func}\nSolved Tasks: {tasks}'
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format="json_object"
        )
        completion = response.choices[0].message.content.strip()
        completion = json.loads(completion)
        # print(completion)
        return self.parse_output(completion['new_function'])
    
    def parse_output(self, res):
        return res
        lines = res.splitlines()
        start = False 
        new_lines = []
        for i in range(len(lines)):
            if start and "```" in lines[i]:
                break
            if start:
                new_lines.append(lines[i])
            if "```python" in lines[i]:
                start = True 
        if new_lines == []:
            return res
        code = "\n".join(new_lines)
        return code
    
class FuncCorrector(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def correct_function(self, func):
        system_prompt = f'''
You are an expert at predicting problems with functions.
The user generated a function to be used by an LLM agent.
Although the function is conceptually fine, since it is called by an LLM agent, it may be incorrect.
The LLM may not call the function with the correct arguments or expected types.
Your task is to predict such problems and correct the function by trying to convert the argument into the required format first.
In case you cannot handle things, make sure top return a proper error message so that someone can look at the logs and interpret the error.
Output a JSON object in the following fomat:
{{
    "new_function": <new_function>,
    "explanation": <explanation>
}}
'''
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": func},
            ],
            response_format="json_object"
        )
        completion = response.choices[0].message.content.strip()
        completion = json.loads(completion)
        # print(completion['new_function'])
        # print(completion, type(completion), res, type(res))
        # kjdf
        return self.parse_output(completion["new_function"])
    
    def parse_output(self, res):
        return res
        lines = res.splitlines()
        start = False 
        new_lines = []
        for i in range(len(lines)):
            if start and "```" in lines[i]:
                break
            if start:
                new_lines.append(lines[i])
            if "```python" in lines[i]:
                start = True 
        code = "\n".join(new_lines)
        return code


class FuncCorrectorFromTrajectories(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def correct_function(self, old_library, new_func, task, old_trajectory, new_trajectory, new_func_def_history):
        system_prompt = f'''
You are an expert at debugging and improving functions.
The user had to solve a task and they had access to a list of tools they could use.
Later, there was an addition to the set of functions, and the user solved the task again.
However, it did not improve the results because the function was not defined properly.
Most errors correcspond to the argument parsing. The input was expected to be of a format but it was not.
You can correct these things by adding some additional code that converts the arguments into the required type.
Your job is to look at the trajectories and improve the newly added function.
Output a JSON object in the following fomat:
{{
    "new_function": <new_function>,
    "explanation": <explanation>
}}
Only change the things that caused the mistake. Do not predict any new changes.
'''
        messages = [{"role": "system", "content": system_prompt}] + new_func_def_history + [{"role": "user", "content": f'Old Library: {old_library}\nNew Function: {new_func}\nTask: {task}\nOld Trajectory: {old_trajectory}\nNew Trajectory: {new_trajectory}'}]
        response = self.llm_client.complete(
            model=self.model_name,
            messages=messages,
            response_format="json_object"
        )
        completion = response.choices[0].message.content.strip()
        completion = json.loads(completion)
        # print(completion)
        # ljkdf
        return self.parse_output(completion["new_function"]), completion["explanation"]
    
    def parse_output(self, res):
        return res
        lines = res.splitlines()
        start = False 
        new_lines = []
        for i in range(len(lines)):
            if start and "```" in lines[i]:
                break
            if start:
                new_lines.append(lines[i])
            if "```python" in lines[i]:
                start = True 
        code = "\n".join(new_lines)
        return code


def get_tool_description(tool):
    """Parses tool metadata and returns a Func object."""
    args = []

    for param_name, param_schema in tool.inputSchema['properties'].items():
        param_type = param_schema.get('type')
        default = param_schema.get('default', None)
        args.append((param_name, param_type, default))

    return Func(
        name=tool.name,
        args=args,
        description=tool.description
    )

def correct_func_from_traj(old_library, new_func, task, old_trajectory, new_trajectory, new_func_def_history):
    agent = FuncCorrectorFromTrajectories()
    return agent.correct_function(old_library, new_func, task, old_trajectory, new_trajectory, new_func_def_history)


def get_new_func(tasks, old_library, verbose=False):
    ####### AGENTS #######
    lib_gen_agent = FunctionSuggestionAgent()
    lib_ranker_agent = LibRankerAgent()
    func_def_agent = FuncDefinitionAgent()
    func_corrector_agent = FuncCorrector()
    
    suggested_funcs = lib_gen_agent.suggest_funcs(tasks, old_library)

    if len(suggested_funcs) > 1:
        rank = lib_ranker_agent.rank_funcs(suggested_funcs)
        func_name = rank.splitlines()[0].strip()
        suggested_func = None
        for func in suggested_funcs:
            if func['name'] == func_name:
                suggested_func = func
                break
        if suggested_func is None:
            print(colored("Function not found", 'red'))
            for func in suggested_funcs:
                print(colored(func['name'], 'red'))
            return
    else:
        suggested_func = suggested_funcs[0]
    
    if verbose:
        print(colored(f'Suggested function name: {suggested_func['name']}', 'blue'))
        

    new_func = func_def_agent.define_func(old_library, suggested_func, tasks)
    if verbose:
        print(colored(f'Proposed function definition:\n{new_func}', 'yellow'))

    new_func = func_corrector_agent.correct_function(new_func)
    if verbose:
        print(colored(f'Corrected function definition:\n{new_func}', 'green'))

    return suggested_func['name'], new_func

def main():
    ########## CONFIG ##########
    mcp_client = 'agent_verify/WebVoyager/AllRecipes.py'
    logs_folder = "agent_verify/WebVoyager/logs_with_results"
    task_file = "agent_verify/WebVoyager/WebVoyager_data.jsonl"
    task_filter = "Allrecipes"
    
    ########## TOOLS AND TASKS##########
    tools = get_tools(mcp_client)
    library = Library(tools).get_funcs()
    tasks = get_tasks(logs_folder, task_file, task_filter)
    tasks = tasks[:5]

    ########## AGENTS ##########
    lib_gen_agent = FunctionSuggestionAgent()
    lib_ranker_agent = LibRankerAgent()
    func_def_agent = FuncDefinitionAgent()
    func_corrector_agent = FuncCorrector()
    func_corrector_agent_from_traj = FuncCorrectorFromTrajectories()

    suggested_funcs = lib_gen_agent.suggest_funcs(tasks, library)
    print(colored('Suggested funcs:', 'green'))
    for f in suggested_funcs:
        print(colored(f, 'green'))

    if len(suggested_funcs) > 1:
        rank = lib_ranker_agent.rank_funcs(suggested_funcs)
        func_name = rank.splitlines()[0].strip()
        print(colored(func_name, 'blue'))
        suggested_func = None
        for func in suggested_funcs:
            if func['name'] == func_name:
                suggested_func = func
                break
        if suggested_func is None:
            print(colored("Function not found", 'red'))
            for func in suggested_funcs:
                print(colored(func['name'], 'red'))
            return
    else:
        suggested_func = suggested_funcs[0]

    
    new_func = func_def_agent.define_func(library, suggested_func, tasks)
    print(colored(new_func, 'yellow'))

    new_func = func_corrector_agent.correct_function(new_func)
    print(colored(new_func, 'blue'))
    # with open(f"dsl_gen/generated_library/{suggested_func['name']}.py", "w", encoding="utf-8") as f:
    #     f.write(new_func)

    return new_func, suggested_func['name']




if __name__ == '__main__':
    main()