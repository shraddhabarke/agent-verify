import os 
import json
import asyncio

from fastmcp import Client
from termcolor import colored

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
        # self.funcs = [func for func in funcs if isinstance(func, Func)]
        self.funcs = [func for func in funcs]

    def add_func(self, func):
        if isinstance(func, Func):
            self.funcs.append(func)

    def get_funcs(self):
        return self.funcs



def get_tool_description(tool):
    """formats tool description from MCP server into a concise form for LLM prompt"""
    param_str = ''
    i = 0
    for p in tool.inputSchema['properties'].keys():
        type = tool.inputSchema['properties'][p]['type']
        s = f'{p}:{type}'

        if 'default' in tool.inputSchema['properties'][p].keys():
            s += f' = {tool.inputSchema['properties'][p]["default"]}'
        
        if i > 0:
            param_str += ', '
        i += 1
        param_str += s
    desc = f"-{tool.name}({param_str}): {tool.description}"
    return desc

async def get_tools_(mcp_server):
    async with Client(mcp_server) as mcp_client:
        tools = await mcp_client.list_tools()
        tool_descriptions = ([
            get_tool_description(tool) for tool in tools
        ])
        return tool_descriptions
    
def get_tools(mcp_server):
    return asyncio.run(get_tools_(mcp_server))
    
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

def get_tasks_only(task_file, task_filter='Allrecipes'):
    tasks = []
    with open(task_file, 'r', encoding='utf-8') as f:
        task_data = [json.loads(line) for line in f if line.strip()]
    for task in task_data:
        if task['web_name'] != task_filter:
            continue 
        task_id = task['id']
        intent = task['ques']
        tasks.append({"id": task_id, "query": intent})
    return tasks

def create_file(mcp_server_old, mcp_server_new, func_def, verbose=False):
    with open(mcp_server_old, "r") as src:
        lines = src.readlines()

    top_lines, last_lines = lines[:-2], lines[-2:]
    func_lines = [f'{line}\n' for line in func_def.splitlines()]
    new_lines = top_lines + ['@mcp.tool()\n'] + func_lines + last_lines
    new_code = ''.join(new_lines)
    if verbose:
        print(colored(new_code, 'red'))
    with open(mcp_server_new, "w") as dst:
        dst.writelines(new_code)
