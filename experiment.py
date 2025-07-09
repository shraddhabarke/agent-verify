import dsl_gen.lib_gen as lib_gen
import agent_verify.WebVoyager.MCPAgent as mcp_agent
from termcolor import colored
from dsl_gen.utils import *
from dsl_gen.improve_trajectories import improve_trajectories, check_trajectory

MAX_REFINEMENT_TRIES = 5

def main():
    original_logs_with_results = "agent_verify/WebVoyager/logs_with_results"
    original_logs_without_results = "agent_verify/WebVoyager/logs"
    improved_logs_folder = "agent_verify/WebVoyager/improved_logs"
    task_file = "agent_verify/WebVoyager/WebVoyager_data.jsonl"
    task_filter = "Allrecipes"
    original_mcp_server = 'agent_verify/WebVoyager/AllRecipes.py'
    new_mcp_server = 'agent_verify/WebVoyager/AllRecipes_test.py'
    tasks_with_original_trajectories = get_tasks(original_logs_with_results, task_file, task_filter)
    
    chunk_size = 5
    i = -chunk_size
    iteration = 0
    while(True):
        iteration += 1
        print(iteration)
        i+=chunk_size
        
        ######### TASKS AND TOOLS #######
        tools = get_tools(original_mcp_server)
        old_library = Library(tools).get_funcs()
        tasks = tasks_with_original_trajectories[i:i+chunk_size]
        
        old_mcp_server = os.path.normpath('agent_verify/WebVoyager/AllRecipes_test.py')
        new_mcp_server = os.path.normpath('agent_verify/WebVoyager/AllRecipes_test2.py')
        
        ########## GENERATE NEW FUNCTION ##########
        new_func_name, new_func_def = lib_gen.get_new_func(tasks, old_library)

        print(colored(f'New function proposed: {new_func_def}', 'blue'))
        
        
        trial = 0
        break_flag = False
        while(break_flag or trial < MAX_REFINEMENT_TRIES):
            if trial > 0:
                xjhg
            trial += 1
            ########## IMPROVE TRAJECTORIES ##########
            new_library = old_library + [new_func_def]
            create_file(old_mcp_server, new_mcp_server, new_func_def)
            client = Client(new_mcp_server)
            improve_trajectories(tasks, client, old_library, new_library, improved_logs_folder, chunk_size)
            traj_results = []
            for j in range(chunk_size):
                # print(j)
                trajectory_file = os.path.normpath(f"{improved_logs_folder}/log_{tasks[j]['id']}.txt")
                trajectory = open(trajectory_file, encoding='utf-8').read()
                traj_results.append(check_trajectory(trajectory, new_func_name))
            
            if len(traj_results) == 0:
                break_flag = True
                break
            index = -1
            for j in range(len((traj_results))):
                if traj_results[j] == 2:
                    index = j
                    break
            if index == -1:
                break_flag = True
                break
            task = tasks[index]['query']
            old_trajectory_file = os.path.normpath(f"{original_logs_with_results}/log_{tasks[i - chunk_size + index]['id']}.txt")
            new_trajectory_file = os.path.normpath(f"{improved_logs_folder}/log_{tasks[i - chunk_size + index]['id']}.txt")
            old_trajectory = open(old_trajectory_file, encoding='utf-8').read()
            new_trajectory = open(new_trajectory_file, encoding='utf-8').read()
            new_func_def = lib_gen.correct_func_from_traj(old_library, new_func_def, task, old_trajectory, new_trajectory)
        
        if break_flag:
            with open(new_mcp_server, 'r', encoding='utf-8') as src, open(old_mcp_server, 'w', encoding='utf-8') as dst:
                dst.write(src.read())


if __name__ == "__main__":
    # new_mcp_server = 'agent_verify/WebVoyager/AllRecipes_test.py'
    # task_file = "agent_verify/WebVoyager/WebVoyager_data.jsonl"
    # logs_folder = "agent_verify/WebVoyager/logs_with_results"
    # improved_logs_folder = "agent_verify/WebVoyager/improved_logs"
    # new_func = 'filter_recipes'
    # task_id = 'Allrecipes--1'
    # tasks = get_tasks_only(task_file, task_filter='Allrecipes')
    # task = tasks[1]['query']
    # old_trajectory_file = os.path.normpath(f"{logs_folder}/log_{task_id}.txt")
    # new_trajectory_file = os.path.normpath(f"{improved_logs_folder}/log_{task_id}.txt")
    # old_trajectory = open(old_trajectory_file, encoding='utf-8').read()
    # new_trajectory = open(new_trajectory_file, encoding='utf-8').read()
    # tools = get_tools(new_mcp_server)
    # old_library = Library(tools).get_funcs()
    # new_func = lib_gen.correct_func_from_traj(old_library, new_func, task, old_trajectory, new_trajectory)
    # print(colored(new_func, 'yellow'))
    main()
