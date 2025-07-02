from get_index import AgentIndex
from get_intent import Intents
from gen_specs import gen_output_spec, get_allowed_apis

amazon_index = AgentIndex('amazon_crawled.yaml')
intents = Intents()
intents.filter(['web_name'], ['Amazon'])
print(gen_output_spec(intents.loc(0)))
print(get_allowed_apis(intents.loc(0), amazon_index.get_verbs()))