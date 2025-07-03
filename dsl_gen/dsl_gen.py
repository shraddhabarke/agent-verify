import os
import json

from termcolor import colored

from agent_verify.agent import Agent 

class DslGeneratorAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def generate_dsl(self, intents):
        system_prompt = f'''
You are an expert at generating DSLs from intents.
You will be given a list of intents.
Your task is to generate a DSL that can represent most of the intents in the list.
Try to write thew grammar in BNF format.
Keep in mind the following guidelines:
1. Do not makie the DSL too long.
2. Make sure that the DSL does not overfit the intents by hard coding any names etc.
3. Make sure you use proper nouns just as variables and not hard code them.
4. You need to be smart to not include English phrases into the DSL. Rather design formal keywords to capture their semantics.
Do not output an explanation or anything else.
'''
        user_prompt = f"Intents: {"\n".join(f"Intent {i}: {intent}" for i, intent in enumerate(intents))}"
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return completion
    
class DSLImprover(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def improve_dsl(self, dsl, intent, formal_intent, comment):
        system_prompt = f'''
You are an expert at creating DSLs. 
You will be given a DSL, a natural language query and its corresponding specification in the DSL.
You will also be given a comment on why the formal specification is not aligned with the DSL.
Your task is to improve the DSL based on the comment and the query.
Try to write thew grammar in BNF format.
Keep in mind the following guidelines:
1. Do not makie the DSL too long.
2. Make sure that the DSL does not overfit the intents by hard coding any names etc.
3. Make sure you use proper nouns just as variables and not hard code them.
4. You need to be smart to not include English phrases into the DSL. Rather design formal keywords to capture their semantics.
5. While you improve the DSL, make sure to not just add additional constructs. Try to adjust the previous DSL to accomodate the new intent.
Do not output an explanation or anything else.
'''
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'Current DSL: {dsl}\nQuery: {intent}\nFormal Specification: {formal_intent}\nComment: {comment}'},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return completion

class NlToDslAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def convert_to_dsl(self, intent, dsl):
        system_prompt = f'''
You are an expert at converting natural language to DSLs.
You will be given a natural language query and a DSL.
Your task is to convert the query into a formal specification in the DSL.
Just write the formal specification and nothing else.
'''
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'Query: {intent}\nDSL: {dsl}'},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return completion
    
class DSLCheckerAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def check_dsl(self, dsl, intent, formal_intent):
        system_prompt = f'''
You are an expert at checking DSLs.
You will be given a DSL, a query in natural language and its corresponding specification in the DSL. 
You task is to check if the specification correctly fits the DSL or not.
There can be 3 answers.
Output 1 is the specification is correct w.r.t the DSL.
Output 2 is the DSL is not sufficient to represent the specification.
Output 3 is the specification is not correct but the DSL is sufficient.
In the next line also output the explanation if you output 2 or 3.
'''
        user_message = f'DSL: {dsl}\nQuery: {intent}\nFormal Specification: {formal_intent}'
        response = self.llm_client.complete(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        completion = response.choices[0].message.content.strip()
        return completion

def get_intents(task_file, task_filter='Allrecipes'):
    with open(task_file, 'r', encoding='utf-8') as f:
        task_data = [json.loads(line) for line in f if line.strip()]
    intents = [task['ques'] for task in task_data if task['web_name'] == task_filter]
    return intents

if __name__ == '__main__':
    dsl_generator_agent = DslGeneratorAgent()
    folder_path = "agent_verify/WebVoyager"
    task_file = os.path.join(folder_path, 'WebVoyager_data.jsonl')
    intents = get_intents(task_file)
    dsl = dsl_generator_agent.generate_dsl(intents)
    
    print(colored(f"Generated DSL: {dsl}", 'green'))

    nl_to_dsl_agent = NlToDslAgent()
    formal_intent = nl_to_dsl_agent.convert_to_dsl(intents[0], dsl)
    print(colored(f"DSL for intent {intents[0]}: {formal_intent}", 'yellow'))
    
    
    dsl_checker_agent = DSLCheckerAgent()
    validation = dsl_checker_agent.check_dsl(dsl, intents[0], formal_intent)
    print(colored(f"Validation for intent {intents[0]}: {validation}", 'red'))

    dsl_improver_agent = DSLImprover()
    improved_dsl = dsl_improver_agent.improve_dsl(dsl, intents[0], formal_intent, validation)
    print(colored(f"Improved DSL for intent {intents[0]}: {improved_dsl}", 'blue'))