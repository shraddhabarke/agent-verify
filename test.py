import dsl_gen.lib_gen as lib_gen
import agent_verify.WebVoyager.MCPAgent as mcp_agent
from termcolor import colored
from dsl_gen.utils import *

def get_func(func_name, func_def):
    lines = func_def.splitlines()
    new_lines = []
    start = False
    indent_level = None

    for line in lines:
        if not start and line.strip().startswith(f"def {func_name}"):
            start = True
            indent_level = len(line) - len(line.lstrip())
            new_lines.append(line)
        elif start:
            current_indent = len(line) - len(line.lstrip())
            if line.strip() and current_indent <= indent_level and line.lstrip().startswith("def "):
                # Next top-level function
                break
            new_lines.append(line)
    
    return "\n".join(new_lines)





def main():
    mcp_server_old = 'agent_verify/WebVoyager/AllRecipes.py'
    mcp_server_new = 'agent_verify/WebVoyager/AllRecipes_test.py'

    new_func, new_func_name = lib_gen.main()
    new_func_name = new_func_name.split(' ')[0]
    print(colored(new_func_name, 'green'), colored(new_func, 'green'))
    # ldkfh
    new_func_def = get_func(new_func_name, new_func)
    print(colored(new_func_def, 'blue'))
    create_file(mcp_server_old, mcp_server_new, new_func_def)

    # mcp_agent.main(mcp_server_new)


if __name__ == '__main__':
    main()
