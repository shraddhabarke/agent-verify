import os 
import json
import asyncio

from fastmcp import Client

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