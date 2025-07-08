import os
import json
import asyncio
from fastmcp import Client
from termcolor import colored
from agent_verify.agent import Agent
from dsl_gen.utils import *

class Func():
    def __init__(self, name, args, description):
        self.name = name
        self.args = args
        self.description = description

    def __str__(self):
        arg_lines = []
        for name, typ, default in self.args:
            if default is not None:
                arg_lines.append(f"  - {name}: {typ} (default={default})")
            else:
                arg_lines.append(f"  - {name}: {typ}")
        args_formatted = "\n".join(arg_lines) if arg_lines else "  (no arguments)"
        
        return (
            f"Function Name: {self.name}\n"
            f"Function Arguments:\n{args_formatted}\n"
            f"Function Description: {self.description}\n"
        )
    
    def __repr__(self):
        return self.__str__()
    
class Library():
    def __init__(self, funcs):
        self.funcs = [func for func in funcs if isinstance(func, Func)]

    def add_func(self, func):
        if isinstance(func, Func):
            self.funcs.append(func)

    def get_funcs(self):
        return self.funcs

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
Output only a python code implementation of the function. Do not give any examples or explanations.
'''
        user_message = f'Current available functions: {library}\nNew function: {new_func}\nSolved Tasks: {tasks}'
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return self.parse_output(completion)
    
    def parse_output(self, res):
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
    
class FuncCorrector(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def correct_function(self, func):
        system_prompt = f'''
You are an expert at prediucting problems with functions.
The user generated a function to be used by an LLM agent.
Although the function is conceptually fine, since it is called by an LLM agent, it may be incorrect.
The LLM may not call the function with the correct arguments or expected types.
Your task is to predict such problems and correct the function.
When you check the argument types, do not just add a try catch. But try to convert the argument into the required format first.
Make sure top return a proper error message in case of an error or an empty output.
Output only a python code implementation of the function. Do not give any examples or explanations.
'''
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": func},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return self.parse_output(completion)
    
    def parse_output(self, res):
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