from trapi_infer import client 


class Output:
    system_prompt = \
'''
You are a useful assitant who is an expert of formal methods.
I have a task from a client that would be solved by a software. 
Can you rewrite the specifications in the formally in a propositional logic query?
Just write the final answer. Do not write any reasoning or explanation. 
'''
    example1 = {
        'intent': 'Provide a recipe for vegetarian lasagna with more than 100 reviews and a rating of at least 4.5 stars suitable for 6 people.',
        'specification': '''
Recipe
    - reviews > 100
    - rating >= 4.5
    - suitable_for_people(6)
'''
    }

    example2 = {
        'intent': 'Find a recipe for a vegetarian lasagna that has at least a four-star rating and uses zucchini.',
        'specification': '''
Recipe
    - vegetarian
    - vegetarian
    - rating >= 4
    - uses(zuchini)
'''
    }

    examples = [example1, example2]


class Program:
    system_prompt = '''
You are a useful assitant who is an expert of formal methods.
I have a task from a client that would be solved by a software.
We want to restirct the software to only a set of actions.
Can you shortlist the set of actions that might be needed to solve the task. 
You just need to shortlist from an exhaustive set of allowed actions.
Just write the final answer. Do not write any reasoning or explanation.
'''

    examples = []



model_name = 'gpt-4o'

def gen_output_spec(intent):
    messages=[
        {"role": "system", "content": Output.system_prompt}
    ]
    for i in range(len(Output.examples)):
        messages.append({'role': 'user', 'content': Output.examples[i]['intent']})
        messages.append({'role': 'assistant', 'content': Output.examples[i]['specification']})
    messages.append({'role': 'user', 'content': intent})
    
    # for message in messages:
    #     print(message)

    print(f'Generating the specs for {intent}')

    response = client.complete(model=model_name, messages=messages)
    response_content = response.choices[0].message.content
    return response_content  

def get_allowed_apis(intent, verbs):
    messages=[
        {"role": "system", "content": Program.system_prompt},
        {"role": "user", "content": f"The set of possible actions is {verbs}"},
        {"role": "user", "content": f"The task is {intent}"}
    ]

    print(f'Generating the relevant api calles for {intent}')
    response = client.complete(model=model_name, messages=messages)
    response_content = response.choices[0].message.content
    return response_content  