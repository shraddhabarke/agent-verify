import json
import traceback
from mcp.types import TextContent, ImageContent
from fastmcp import Client, FastMCP

class WebVoyagerEnv:
    def __init__(self):
        pass

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
    
    async def call_mcp_tool(self, mcp_client:Client, function_name, function_args):
        """ Calls a function on the MCP server and returns the result."""
        try:
            resp_items = []
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