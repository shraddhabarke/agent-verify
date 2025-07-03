import os
import json
import asyncio
from fastmcp import Client
from termcolor import colored
from agent_verify.agent import Agent

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
You need to suggest more functions that can be added to this library.
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
        print(completion)
        res = self.parse_result(completion)
        print(res)
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
'''
        user_message = f'Current available functions: {library}\nNew function: {new_func}\nSolved Tasks: {tasks}'
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        # print(system_prompt)
        # print(user_message)
        completion = response.choices[0].message.content.strip()
        return completion


def get_tasks(logs_folder, task_file, task_filter='Allrecipes'):
    tasks = []
    traj_files = os.listdir(logs_folder)
    with open(task_file, 'r', encoding='utf-8') as f:
        task_data = [json.loads(line) for line in f if line.strip()]
    for task in task_data:
        if task['web_name'] != task_filter:
            continue 
        task_id = task['id']
        intent = task['ques']
        traj_file = f"log_{task_id}.txt"
        if traj_file in traj_files:
            with open(os.path.join(logs_folder, traj_file), "r") as f:
                traj = '\n'.join(f.read().splitlines()[2:])
            tasks.append({"id": task_id, "query": intent, "traj": traj})
    return tasks


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

async def get_tools(mcp_server):
    async with Client(mcp_server) as mcp_client:
        tools = await mcp_client.list_tools()
        tool_descriptions = ([
            get_tool_description(tool) for tool in tools
        ])
        return tool_descriptions


def main():
    mcp_client = 'agent_verify/WebVoyager/AllRecipes.py'
    logs_folder = "agent_verify/WebVoyager/logs"
    task_file = "agent_verify/WebVoyager/WebVoyager_data.jsonl"
    task_filter = "Allrecipes"
    
    tools = asyncio.run(get_tools(mcp_client))
    library = Library(tools).get_funcs()
    tasks = get_tasks(logs_folder, task_file, task_filter)

    lib_gen_agent = FunctionSuggestionAgent()
    lib_ranker_agent = LibRankerAgent()
    func_def_agent = FuncDefinitionAgent()

    suggested_funcs = lib_gen_agent.suggest_funcs(tasks, library)
    print(colored(suggested_funcs, 'green'))

    rank = lib_ranker_agent.rank_funcs(suggested_funcs)
    func_name = rank.splitlines()[0].strip()
    print(colored(func_name, 'blue'))
    suggested_func = None
    for func in suggested_funcs:
        if func['name'] == func_name:
            suggested_func = func
            break

    if suggested_func is None:
        print("Function not found")
        for func in suggested_funcs:
            print(func['name'])
        return
    new_func = func_def_agent.define_func(library, suggested_func, tasks)
    print(colored(new_func, 'yellow'))



if __name__ == '__main__':
    main()