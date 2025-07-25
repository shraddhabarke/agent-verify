import os
import json
from pathlib import Path

def get_all_flash_trajectories(base_path="trajectories/flash"):
    """
    Get a list of all trajectories from Flash result files.
    
    Returns:
        list: A list of dictionaries, each containing trajectory data
    """
    trajectories = []
    
    # Find all result directories
    result_path = Path(base_path)
    
    if not result_path.exists():
        # print(f"Path {base_path} does not exist")
        return trajectories
    
    # Recursively find all JSONL files that are NOT exec_log files
    jsonl_files = list(result_path.rglob("*.jsonl"))
    # Filter out exec_log files - we want the actual trajectory files
    trajectory_files = [f for f in jsonl_files if "__exec_log" in f.name]
    
    # print(f"Found {len(trajectory_files)} trajectory files")
    
    for jsonl_file in trajectory_files:
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                content = f.read()
                trajectory = []
                
                # Split on }{ pattern and reconstruct JSON objects
                parts = content.split('}\n{')
                for i, part in enumerate(parts):
                    if i == 0:
                        # First part, add closing brace if needed
                        if not part.endswith('}'):
                            part += '}'
                    elif i == len(parts) - 1:
                        # Last part, add opening brace if needed
                        if not part.startswith('{'):
                            part = '{' + part
                    else:
                        # Middle parts, add both braces
                        part = '{' + part + '}'
                    
                    # Try to parse each part
                    try:
                        trajectory.append(json.loads(part.strip()))
                    except json.JSONDecodeError:
                        # Skip malformed JSON parts
                        continue
                trajectories.append(trajectory)
            # break
                            
        except Exception as e:
            # print(f"Error reading file {jsonl_file.name}: {e}")
            pass
    
    # print(f"Total trajectories loaded: {len(trajectories)}")
    return trajectories

# Example usage
if __name__ == "__main__":
    # Load all trajectories
    trajectories = get_all_flash_trajectories()
    print(f"Number of trajectories: {len(trajectories)}")
    # if trajectories:
    #     print(f"First trajectory: {(trajectories[0])}")