import dsl_gen.lib_gen as lib_gen
import agent_verify.WebVoyager.MCPAgent as mcp_agent
from termcolor import colored
from dsl_gen.utils import *
from dsl_gen.improve_trajectories import improve_trajectories, check_trajectory
from agent_verify.WebVoyager.MCPAgent import *
from tabulate import tabulate
from test_mcp import *

MAX_REFINEMENT_TRIES = 5

class Metrics:
    def __init__(self):
        pass

    def compute_metrics(old_trajectories, new_trajectories, new_funcs):
        pass




def main():
    original_logs_with_results = "agent_verify/WebVoyager/logs_with_results"
    original_logs_without_results = "agent_verify/WebVoyager/logs"
    improved_logs_folder = "agent_verify/WebVoyager/improved_logs"
    task_file = "agent_verify/WebVoyager/WebVoyager_data.jsonl"
    task_filter = "Allrecipes"
    original_mcp_server = os.path.normpath('agent_verify/WebVoyager/AllRecipes.py')
    old_mcp_server = os.path.normpath('agent_verify/WebVoyager/AllRecipes_test.py')
    new_mcp_server = os.path.normpath('agent_verify/WebVoyager/AllRecipes_test2.py')
    train_tasks = get_tasks(original_logs_with_results, task_file, task_filter)[:24]
    test_tasks = get_tasks_only(task_file, task_filter)[24:]


    open(old_mcp_server, 'w').close()
    create_file(original_mcp_server, old_mcp_server, '')
    
    train_chunck_size = 3
    i = -train_chunck_size
    iteration = 0
    while(True):
        iteration += 1
        print(iteration)
        i+=train_chunck_size
        
        ######### TASKS AND TOOLS #######
        tools = get_tools(old_mcp_server)
        old_library = Library(tools).get_funcs()
        tasks = train_tasks[i:i+train_chunck_size]
        
        # open(new_mcp_server, 'w').close()
        
        ########## GENERATE NEW FUNCTION ##########
        MAX_TRIES_TO_GENERATE_FUNCTION = 3
        new_func_def = ''
        new_func_name = 'filter_recipes'
        function_gen_trial = 0
        while 'def' not in new_func_def and function_gen_trial < MAX_TRIES_TO_GENERATE_FUNCTION:
            new_func_name, new_func_def = lib_gen.get_new_func(tasks, old_library)
            function_gen_trial += 1
    
        print(colored(f'New function proposed: {new_func_def}', 'blue'))
        
        new_func_def_history = [{"role": "user", "content": "Original function: \n" + new_func_def}]

        ########## IMPROVE TRAJECTORIES ##########
        trial = 0
        break_flag = False
        while(break_flag or trial < MAX_REFINEMENT_TRIES):
            trial += 1
            ########## IMPROVE TRAJECTORIES ##########
            new_library = old_library + [new_func_def]
            open(new_mcp_server, 'w').close()
            create_file(old_mcp_server, new_mcp_server, new_func_def)

            traj_results = []
            index = -1
            for j in range(train_chunck_size):
                print(colored(tasks[j]['id'], 'green'))
                new_trajectory_file = os.path.normpath(f"{improved_logs_folder}/log_{tasks[j]['id']}.txt")
                improved_trajectory_logs = improve_trajectories([tasks[j]], new_mcp_server, old_library, new_library)
                trajectory = improved_trajectory_logs[tasks[j]['id']]
                with open(new_trajectory_file, "w", encoding="utf-8") as f:
                    json.dump(trajectory, f, ensure_ascii=False, indent=4)
                
                traj_results.append(check_trajectory(trajectory, new_func_name))
                print(colored(f'Trajectory check results: {traj_results[j]}', 'cyan'))
                if traj_results[j] == 2:
                    break_flag = False
                    index = j
                    break     
            if index==-1:
                break_flag = True
            if break_flag:
                break      
            
            print("wrong trajectory", tasks[index]['id'])
            task = tasks[index]['query']
            old_trajectory_file = os.path.normpath(f"{original_logs_with_results}/log_{tasks[index]['id']}.txt")
            new_trajectory_file = os.path.normpath(f"{improved_logs_folder}/log_{tasks[index]['id']}.txt")
            old_trajectory = open(old_trajectory_file, encoding='utf-8').read()
            old_trajectory = train_tasks[i+index]
            new_trajectory = trajectory

            print(old_trajectory_file)
            print(new_trajectory_file)

            improved_func_def = ''
            function_improvement_trial = 0
            MAX_TRIES_TO_IMPROVE_FUNCTION = 3
            while 'def' not in improved_func_def and function_improvement_trial < MAX_TRIES_TO_IMPROVE_FUNCTION:
                improved_func_def, explanation = lib_gen.correct_func_from_traj(old_library, new_func_def, task, old_trajectory, new_trajectory, new_func_def_history)
                function_improvement_trial += 1
            new_func_def = improved_func_def

            print(colored(f'Corrected proposed function: {new_func_def}', 'green'))
            print(colored(f'Explanation: {explanation}', 'red'))

            new_func_def_history.append({"role": "user", "content": f'Failed task: \n{task}\nOld Trajectory: \n{old_trajectory}\nNew Trajectory: \n{new_trajectory}'})
            new_func_def_history.append({"role": "assistant", "content": f'Corrected function: \n{new_func_def}, Explanation: \n{explanation}'})

        
        if break_flag:
            create_file(new_mcp_server, old_mcp_server, "")

            test_logs = test_mcp(test_tasks, new_mcp_server)
            test_logs_file = f'agent_verify/WebVoyager/test_logs_2/trial_{iteration}.txt'
            with open(test_logs_file, "w", encoding="utf-8") as f:
                json.dump(test_logs, f, ensure_ascii=False, indent=4)
            # with open(test_logs_file, "w", encoding="utf-8") as f:
            #     f.write(repr(test_logs))


if __name__ == "__main__":
    main()