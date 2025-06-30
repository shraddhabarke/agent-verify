import os 
import re
import sys

from agent import Agent 

class IntentFormalizationAgent(Agent):
    def __init__(self):
        super().__init__()

    def get_formal_intent(self, intent):
        system_prompt = f'''
You are an expert at intent formalization.
You will be given a natural language intent description.
Your task is to formalize the intent.
You can structure the output as a json format. You need to choose the keys and values. 
For each value, you must mention the comparison operator.
Some of the keys you may need to use are 
title, rating, rating count, review count, description, prep time, cook time, total time, servings, yield, ingredients, nutrition facts, and directions.
Do not use any other keys. And do not change their spellings.
        '''
        user_prompt = "Provide a recipe for vegetarian lasagna with more than 100 reviews and a rating of at least 4.5 stars suitable for 6 people."
        response = '''
{{
    "object": "recipe",
    "properties": {{
        "rating": {{
            "value": 4.5,
            "comparison": ">="
        }},
        "review_count": {{
            "value": 100,
            "comparison": ">"
        }},
        "servings": {{
            "value": 6,
            "comparison": "="
        }}
    }}
}}'''
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": response},
                {"role": "user", "content": intent},
            ],
        )

        completion = response.choices[0].message.content.strip()

        return completion

def parse_log_file(log_text: str) -> dict:
    parsed = {
        "task": "",
        "steps": [],
        "final_result": {},
        "num_steps": {},
        "goal_achieved": {}
    }

    lines = log_text.strip().splitlines()
    current_step = None

    for line in lines:
        line = line.strip()

        # Task description
        if line.startswith("Executing task:"):
            parsed["task"] = line.replace("Executing task:", "").strip()

        # Step indicator
        elif line.startswith("Step "):
            match = re.match(r"Step (\d+):.*?args (.*)", line)
            if match:
                step_num = int(match.group(1))
                args_str = match.group(2)
                current_step = {
                    "step": step_num,
                    "args": eval(args_str),  # Safe here if logs are trusted; otherwise use `ast.literal_eval`
                }
                parsed["steps"].append(current_step)

        # Reason
        elif line.startswith("Reason:") and current_step is not None:
            current_step["reason"] = line.replace("Reason:", "").strip()

        # Function call
        elif line.startswith("Function Name:") and current_step is not None:
            match = re.match(r"Function Name:\s*(\w+)\s*Function Args:\s*(.*)", line)
            if match:
                current_step["function"] = match.group(1)
                current_step["args"] = eval(match.group(2))

        # Final result
        elif line.startswith("Final Result:"):
            parsed["final_result"]["title"] = line.replace("Final Result:", "").strip()
        elif line.startswith("Rating:"):
            parsed["final_result"]["rating"] = float(line.split(":", 1)[1].strip())
        elif line.startswith("Review count:"):
            parsed["final_result"]["review_count"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Servings:"):
            parsed["final_result"]["servings"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Ingredients:"):
            parsed["final_result"]["ingredients"] = line.replace("Ingredients:", "").strip()
        elif line.startswith("Directions:"):
            parsed["final_result"]["directions"] = line.replace("Directions:", "").strip()

        # Summary
        elif line.startswith("Steps taken:"):
            parsed["num_steps"] = int(re.search(r'\d+', line).group())
            parsed["goal_achieved"] = "True" in line

    return parsed




def get_logs(log_path):
    logs = {}
    counter = 0
    for log_file in os.listdir(log_path):
        if log_file.startswith('log_'):
            file_path = os.path.join(log_path, log_file)
            if os.path.isfile(file_path):
                with open(file_path, 'r') as f:
                    log = parse_log_file(f.read())
                    log['filename'] = log_file
                    logs[counter] = log
                    counter += 1
    return logs

def get_formal_intent(logs):
    agent = IntentFormalizationAgent()

    for i in range(len(logs)):
        log = logs[i]
        print(log['filename'])
        log_file = f"formal_intents/{log['filename']}"
        if os.path.exists(log_file):
            continue
        sys.stdout = open(log_file, 'w', encoding='utf-8')  # Suppress stdout for cleaner output
        user_input = log['task']
        print(f"Executing task: {user_input}")
        result = agent.get_formal_intent(user_input)
        print(result)
        sys.stdout.close()  # Close the suppressed stdout
        sys.stdout = sys.__stdout__  # Restore original stdout



def main():
    logs_path = 'logs/'
    logs = get_logs(logs_path)
    get_formal_intent(logs)

    

if __name__ == '__main__':
    main()