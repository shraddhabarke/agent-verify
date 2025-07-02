import json
import os
from openai import AzureOpenAI
from fastmcp import Client, FastMCP
import asyncio
from dotenv import load_dotenv
from azure.identity import get_bearer_token_provider, AzureCliCredential
from mcp.types import TextContent, ImageContent
import traceback
import re
import sys

from azure.ai.inference import ChatCompletionsClient
from azure.identity import DefaultAzureCredential, ChainedTokenCredential, AzureCliCredential
import os

from agent import Agent

# An AI agent that uses Azure OpenAI to call functions from a MCP server
class WebVoyagerAgent(Agent):
    # def __init__(self):
    #     load_dotenv()
    #     self.llm_client = AzureOpenAI(
    #         api_version="2024-05-01-preview",
    #         azure_endpoint=os.environ['OPENAI_ENDPOINT'],
    #         azure_ad_token_provider=get_bearer_token_provider(
    #             AzureCliCredential(),
    #             "https://cognitiveservices.azure.com/.default"
    #         )
    #     )
    
    def __init__(
            self,
            api_version = '2025-03-01-preview',  # Ensure this is a valid API version see: https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
            model_name = 'gpt-4o',  # Ensure this is a valid model name
            model_version = '2024-11-20',  # Ensure this is a valid model version
            deployment_name = "gpt-4o_2024-11-20", #re.sub(r'[^a-zA-Z0-9-_]', '', f'{model_name}_{model_version}')  # If your Endpoint doesn't have harmonized deployment names, you can use the deployment name directly: see: https://aka.ms/trapi/models
    ):
        super().__init__(api_version, model_name, model_version, deployment_name)
        

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
    
    # def call_llm(self, system_prompt, user_prompt, max_tokens=1000):
    #     """
    #     Send the prompt to Azure OpenAI (GPT-4o) and handle token counting.
    #     Returns the text output from the model.
    #     """
    #     response = self.llm_client.chat.completions.create(
    #         model=os.environ['OPENAI_TEXT_MODEL'],
    #         messages=[
    #             {"role": "system", "content": system_prompt},
    #             {"role": "user", "content": user_prompt},
    #         ],
    #         max_tokens=max_tokens,
    #     )

    #     completion = response.choices[0].message.content.strip()

    #     return completion
    
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
            max_tokens=max_tokens,
        )

        completion = response.choices[0].message.content.strip()

        return completion

    async def call_mcp_tool(self, mcp_client:Client, function_name, function_args):
        """ Calls a function on the MCP server and returns the result."""
        try:
            resp_items = []
            print(f"Function Name: {function_name} Function Args: {function_args}")
            func_response = await mcp_client.call_tool(function_name, function_args)
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

    async def execute_task(self, mcp_server:str, user_task:str):
        """
        Execute a user-defined task by calling the appropriate function from AllRecipes.py.
        Returns the result of the function call.
       """

        goal = user_task.strip()
        history = []
        step = 1
        final_result = None

        mcp_client = Client(mcp_server)

        async with mcp_client:
            tools = await mcp_client.list_tools()
            tool_descriptions = "\n".join([
                self.get_tool_description(tool) for tool in tools
            ])

            system_prompt = self.get_system_prompt(tool_descriptions)

            while True:
                # Ask LLM which function to call next
                user_message = f"Goal: {goal}\nExecution History: {json.dumps(history, indent=2)}"                
                response = self.call_llm(system_prompt, user_message)                
                llm_response = self.fix_json_response(response)
                    
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
                    print(f"Result: {result}")
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

        return {
            "final_result": final_result,
            "step": step - 1,
            "goal_achieved": goal_achieved
            }

    

if __name__ == "__main__":
    task_file = 'WebVoyager_data.jsonl'
    task_filter = 'Allrecipes'
    task_count = 100 # how many tasks that match the filter to execute; put a large number if you want to execute all tasks
    mcp_server = 'AllRecipes.py'


    with open(task_file, 'r', encoding='utf-8') as f:
        task_data = [json.loads(line) for line in f if line.strip()]

    agent = WebVoyagerAgent()
    #user_input = 'Search for a popular Pasta Sauce with more than 1000 reviews and a rating above 4 stars. Create a shopping list of ingredients for this recipe.'
    #result = asyncio.run(agent.execute_task(mcp_server, user_input))
    
    count = task_count
    for task in task_data:
        if task['web_name'] != task_filter:
            continue
        if count <= 0:
            break

        print(task['id'])
        log_file = f"logs_with_intents/log_{task['id']}.txt"
        intent_file = f"formal_intents/log_{task['id']}.txt"
        intent = open(intent_file, encoding="utf-8").read()
        if os.path.exists(log_file):
            continue
        sys.stdout = open(log_file, 'w', encoding='utf-8')  # Suppress stdout for cleaner output
        user_input = task['ques']
        print(f"Executing task: {user_input}")
        result = asyncio.run(agent.execute_task(mcp_server, intent))
        print(f"\nFinal Result: {result['final_result']}")
        print(f"\nSteps taken: {result['step']}, Goal Achieved: {result['goal_achieved']}")

        print("\n" + "="*50 + "\n")
 
        count -= 1
        sys.stdout.close()  # Close the suppressed stdout
        sys.stdout = sys.__stdout__  # Restore original stdout