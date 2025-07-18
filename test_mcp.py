import json
import os
from fastmcp import Client, FastMCP
import asyncio
from mcp.types import TextContent, ImageContent
import traceback
import re
import sys
import argparse
import os

from agent_verify.agent import Agent
from webvoyager_env import WebVoyagerEnv

class WebVoyagerAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env = WebVoyagerEnv()

    def call_llm(self, system_prompt, user_prompt):
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = self.llm_client.complete(model=self.model_name, messages=messages, response_format="json_object")
        completion = response.choices[0].message.content.strip()
        completion = json.loads(completion)
        return completion

    def get_system_prompt(self, tool_descriptions: str) -> str:
        """
        Generate the system prompt for the LLM based on available tools.
        """
        return """You are an AI assistant that helps with completing user task by suggesting tool calls. Based on the user's goal and execution history, decide which function to call next.

Available functions:
TOOL_DESCRIPTIONS

Respond with JSON in this format:
{
    "explanation": "Why this function should be called next",
    "function": "function_name",
    "args": {"arg1": "value1", "arg2": "value2", ...},
    "stop": false,
}

Set "stop": true when (1) the user goal is achieved and no more functions are needed. or (2) when user goal cannot be satisifed.
""".replace('TOOL_DESCRIPTIONS', tool_descriptions)
        
    def get_system_prompt_for_final_answer(self):
        return """You are an AI assistant that helps extracting relevant information from a large document.
Given a user goal and a result given by a tool, extract only the part of the tool result that satisfies the user goal. Keep the response concise and relevant.

Respond with JSON in this format:
{
    "explanation": "why this answer satisfies user goal",
    "answer": "extracted answer that satisfies the user goal",
    "goal_achieved": false,
}
Set "goal_achieved": true when the user goal is achieved, otherwise false.
"""

    async def execute_task(self, mcp_server:str, user_task:str):
        """
        Execute a user-defined task by calling the appropriate function from AllRecipes.py.
        Returns the result of the function call.
       """
        task_log = {}
        goal = user_task.strip()
        history = []
        step = 0
        final_result = None

        mcp_client = Client(mcp_server)

        async with mcp_client:
            tools = await mcp_client.list_tools()
            tool_descriptions = "\n".join([
                self.env.get_tool_description(tool) for tool in tools
            ])
            task_log['tools'] = [tool.name for tool in tools]

            traj = []

            system_prompt = self.get_system_prompt(tool_descriptions)

            while True:
                # Ask LLM which function to call next
                user_message = f"Goal: {goal}\nExecution History: {json.dumps(history, indent=2)}"                
                response = self.call_llm(system_prompt, user_message)           
                llm_response = response     
                
                if not llm_response or llm_response['stop']:
                    user_message = f"Goal: {goal}\nFinal tool response to extract from:\n {json.dumps(final_result, indent=2)}"                
                    llm_response = self.call_llm(self.get_system_prompt_for_final_answer(), user_message)    
                    final_result = llm_response['answer']
                    goal_achieved = llm_response['goal_achieved']
                    explanation = llm_response['explanation']

                    

                    break
                
                func_name = llm_response['function']
                args = llm_response['args']
                explanation = llm_response['explanation']
                result = await self.env.call_mcp_tool(mcp_client, func_name, args)

                traj_step = {
                    "step": step,
                    "function": func_name,
                    "args": args,
                    "explanation": explanation,
                    "result": result
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

        task_log['traj'] = traj
        task_log['goal_achieved'] = goal_achieved
        task_log['explanation'] = explanation
        task_log['final_result'] = final_result
        task_log['steps_taken'] = step  

        return task_log

def test_mcp(task_data, mcp_server='AllRecipes.py'):
    folder_path = "agent_verify/WebVoyager"
    mcp_server = os.path.normpath(mcp_server)
    if not os.path.isfile(mcp_server):  # assume it's relative only if it’s not a file already
        mcp_server = os.path.join(folder_path, mcp_server)

    logs = {}
    agent = WebVoyagerAgent()
    for task in task_data:
        user_input = task['query']
        task_log = asyncio.run(agent.execute_task(mcp_server, user_input))
        logs[task['id']] = task_log
    return logs

