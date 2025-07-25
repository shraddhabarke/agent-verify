import os
import json
from pathlib import Path

def get_all_bfcl_trajectories(base_path="trajectories/bfcl/result"):
    """
    Get a list of all trajectories from BFCL result files.
    
    Returns:
        list: A list of dictionaries, each containing trajectory data
    """
    trajectories = []
    
    # Find all result directories
    result_path = Path(base_path)
    
    if not result_path.exists():
        # print(f"Path {base_path} does not exist")
        return trajectories
    
    # Iterate through all subdirectories (model folders)
    for model_dir in result_path.iterdir():
        if model_dir.is_dir():
            # print(f"Processing model directory: {model_dir.name}")
            
            # Find all JSON result files in this model directory
            for json_file in model_dir.glob("*.json"):
                # print(f"  Loading file: {json_file.name}")
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        # Each line in the file is a separate JSON object (trajectory)
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if line:  # Skip empty lines
                                try:
                                    trajectory = json.loads(line)
                                    # Add metadata about source
                                    # trajectory['source_model'] = model_dir.name
                                    # trajectory['source_file'] = json_file.name
                                    # trajectory['line_number'] = line_num
                                    trajectory = trajectory['result']
                                    trajectories.append(trajectory)
                                except json.JSONDecodeError as e:
                                    # print(f"    Error parsing line {line_num} in {json_file.name}: {e}")
                                    pass
                                    
                except Exception as e:
                    # print(f"  Error reading file {json_file.name}: {e}")
                    pass
    
    # print(f"\nTotal trajectories loaded: {len(trajectories)}")
    return trajectories
# Example usage
if __name__ == "__main__":
    # Load all trajectories
    trajectories = get_all_bfcl_trajectories()
    