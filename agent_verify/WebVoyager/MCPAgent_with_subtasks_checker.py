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
from termcolor import colored
from agent_verify.agent import Agent

def read_formalized_tasks(task_filter='Allrecipes'):
    file_name = f'formalized_tasks_{task_filter}.json'
    tasks = json.loads(open(file_name).read())
    new_tasks = []
    for task in tasks:
        new_task = []
        for key in task.keys():
            new_task.append(task[key])
        new_tasks.append(new_task)
    return new_tasks

class SubtaskChecker(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def check_subtask(self, history, subtask, constraints):
        system_prompt = f'''
You are a helpful assistant.
A customer is interacting with a customer support agent with their request.
From the customer's request, we have extracted a subtask that must be satisfied somewhere through the solution steps.
Your job is to check whether the specific subtask has yet been solved or not.  
The task also comes with a set of constraints. The task is solved if all the constraints are met.    
We will provide you with the steps taken by the customer agent so far.
We will also provide you with the subtask that needs to be checked.
Return your answer in the following json format:
{{
    "solved": <True or False>,
    "reason": <reason>
}}  
'''
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f'Steps taken: \n{history}\n\nSubtask: \n{subtask}\n\nAssociated constraints: \n{constraints}\n\n'}]
        res = self.llm_client.complete(model = self.model_name, messages=messages, response_format="json_object").choices[0].message['content']
        res = json.loads(res)
        # print(colored(res, 'magenta'))
        return res
    
    def check_subtasks(self, history, subtasks):
        res = [self.check_subtask(history, subtask['task'], subtask['constraints']) for subtask in subtasks]
        return [i['solved'] for i in res], [i['reason'] for i in res]

# An AI agent that uses Azure OpenAI to call functions from a MCP server
class WebVoyagerAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        

    def get_tool_description(self, tool):
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
    
    def call_llm(self, system_prompt, user_prompt, max_tokens=1000):
        """
        Send the prompt to LLM and handle token counting.
        Returns the text output from the model.
        """
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # max_tokens=max_tokens,
        )

        completion = response.choices[0].message.content.strip()

        return completion

    async def call_mcp_tool(self, mcp_client:Client, function_name, function_args):
        """ Calls a function on the MCP server and returns the result."""
        try:
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

    def get_system_prompt(self, tool_descriptions: str) -> str:
        """
        Generate the system prompt for the LLM based on available tools.
        """
        return """You are an AI assistant that helps with completing user task by suggesting tool calls. Based on the user's goal and execution history, decide which function to call next.

Available functions:
TOOL_DESCRIPTIONS

Respond with JSON in this format:
{
    "function": "function_name",
    "args": {"arg1": "value1", "arg2": "value2"},
    "stop": false,
    "explanation": "Why this function should be called next",
}

Set "stop": true when (1) the user goal is achieved and no more functions are needed. or (2) when user goal cannot be satisifed.
""".replace('TOOL_DESCRIPTIONS', tool_descriptions)
        
    def get_system_prompt_for_final_answer(self):
        return """You are an AI assistant that helps extracting relevant information from a large document.
Given a user goal and a result given by a tool, extract only the part of the tool result that satisfies the user goal. Keep the response concise and relevant.

Respond with JSON in this format:
{
    "answer": "extracted answer that satisfies the user goal",
    "goal_achieved": false,
    "explanation": "why the answer satisfies user goal",
}
Set "goal_achieved": true when the user goal is achieved, otherwise false.
"""

    async def execute_task(self, mcp_server:str, user_task:str, subtasks):
        """
        Execute a user-defined task by calling the appropriate function from AllRecipes.py.
        Returns the result of the function call.
       """

        goal = user_task.strip()
        history = []
        step = 1
        final_result = None

        mcp_client = Client(mcp_server)
        subtask_checker = SubtaskChecker()


        async with mcp_client:
            tools = await mcp_client.list_tools()
            tool_descriptions = "\n".join([
                self.get_tool_description(tool) for tool in tools
            ])

            system_prompt = self.get_system_prompt(tool_descriptions)
            # print(colored(f"Goal: {goal}", 'blue'))
            # print(colored(f"Subtasks: {subtasks}", 'magenta'))

            while True:
                # Ask LLM which function to call next
                user_message = f"Goal: {goal}\nExecution History: {json.dumps(history, indent=2)}"                
                response = self.call_llm(system_prompt, user_message)                
                llm_response = self.fix_json_response(response)
                
                # print("Response:", response)
                # print("LLM Response:", llm_response)
                # Expected llm_response: {"function": "func_name", "args": {...}, "stop": bool, "explanation": str}
                if not llm_response or llm_response.get("stop"):
                    print("\nTask complete or LLM indicated to stop.")
                    user_message = f"Goal: {goal}\nFinal tool response to extract from:\n {json.dumps(final_result, indent=2)}"                
                    response = self.call_llm(self.get_system_prompt_for_final_answer(), user_message)                
                    llm_response = self.fix_json_response(response)
                    final_result = llm_response.get("answer", None)
                    goal_achieved = llm_response.get("goal_achieved", False)
                    explanation = llm_response.get("explanation", "")
                    break
                
                if llm_response.get("answer"):
                    print(f"\nLLM provided an answer: {llm_response['answer']}")
                    result = llm_response['answer']
                else:
                    func_name = llm_response.get("function")
                    args = llm_response.get("args", {})
                    explanation = llm_response.get("explanation", "")
                    print(f"\nStep {step}: LLM suggests calling '{func_name}' with args {args}")
                    if explanation:
                        print(f"Reason: {explanation}")
                    
                    result = await self.call_mcp_tool(mcp_client, func_name, args)
                    # print(f"Result: {result}")
                # print(f"Result: {result}")
                final_result = result
                
                # Update history
                history.append({
                    "step": step,
                    "function": func_name,
                    "args": args,
                    "result": result
                })
                step += 1

                subtasks_solved, subtasks_solved_reason = subtask_checker.check_subtasks(history, subtasks)
                print(f'Subtasks: {subtasks}')
                print(f'Subtasks Solved: {subtasks_solved}')
                print(f'Subtasks Solved Reason: {subtasks_solved_reason}')
                # kdkdjf

                for i in range(len(subtasks_solved)-1, -1, -1):
                    if subtasks_solved[i]:
                        del subtasks[i]

        # kudhf
        return {
            "final_result": final_result,
            "step": step - 1,
            "goal_achieved": goal_achieved
            }

def main(mcp_server='AllRecipes.py', logs_folder='logs_with_subtasks'):
    folder_path = "agent_verify/WebVoyager"
    task_file = os.path.join(folder_path, 'WebVoyager_data.jsonl')
    # mcp_server = os.path.join(folder_path, mcp_server)
    mcp_server = os.path.normpath(mcp_server)
    if not os.path.isfile(mcp_server):  # assume it's relative only if it’s not a file already
        mcp_server = os.path.join(folder_path, mcp_server)

    # mcp_server = "agent_verify/WebVoyager/mcp_server/server.py"
    task_count = 1000 # how many tasks that match the filter to execute; put a large number if you want to execute all tasks
    task_filter = 'Allrecipes'
    agent = WebVoyagerAgent()

    formalized_tasks_all = read_formalized_tasks(task_filter)


    with open(task_file, 'r', encoding='utf-8') as f:
        task_data = [json.loads(line) for line in f if line.strip()]
    
    count = task_count
    for task_index, task in enumerate(task_data):
        if task['web_name'] != task_filter:
            continue
        if count <= 0:
            break

        print(task['id'])
        subtasks = formalized_tasks_all[task_index]
        log_file = os.path.join(folder_path, f"{logs_folder}/log_{task['id']}.txt")
        intent_file = os.path.join(folder_path, f"formal_intents/log_{task['id']}.txt")
        intent = open(intent_file, encoding="utf-8").read()
        if os.path.exists(log_file):
            continue
        sys.stdout = open(log_file, 'w', encoding='utf-8')  # Suppress stdout for cleaner output
        user_input = task['ques']
        print(f"Executing task: {user_input}")
        result = asyncio.run(agent.execute_task(mcp_server, intent, subtasks))
        print(f"\nFinal Result: {result['final_result']}")
        print(f"\nSteps taken: {result['step']}, Goal Achieved: {result['goal_achieved']}")

        print("\n" + "="*50 + "\n")
 
        count -= 1
        sys.stdout.close()  # Close the suppressed stdout
        sys.stdout = sys.__stdout__  # Restore original stdout

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mcp_server", nargs="?", default="AllRecipes.py", help="Optional script name")
    parser.add_argument("logs_folder", nargs="?", default="logs_with_subtasks", help="Optional script name")
    args = parser.parse_args()

    assert(args.mcp_server in ["AllRecipes_test.py", "AllRecipes.py"])    

    main(args.mcp_server, args.logs_folder)