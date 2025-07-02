import yaml
import os

class Variables:
    def __init__(self, variables):
        self.variables = variables

    def __repr__(self):
        return f"Variables(variables={self.variables})"
    
class TextMarker:
    def __init__(self, text, match_type, where, element_id):
        self.text = text
        self.match_type = match_type
        self.where = where
        self.element_id = element_id

    def __repr__(self):
        return (f"TextMarker(text={self.text!r}, match_type={self.match_type!r}, "
                f"where={self.where!r}, element_id={self.element_id!r})")
    
class Atom:
    def __init__(self, id, description, markers, element_ids):
        self.id = id
        self.description = description
        self.markers = markers  # This will be a list of TextMarker instances
        self.element_ids = element_ids

    def __repr__(self):
        return (f"Atom(id={self.id!r}, description={self.description!r}, "
                f"markers={self.markers!r}, element_ids={self.element_ids!r})")
    
class State:
    def __init__(self, id, url, description, atoms):
        self.id = id
        self.url = url
        self.description = description
        self.atoms = atoms  # This will be a list of Atom instances (or references)

    def __repr__(self):
        return (f"State(id={self.id!r}, url={self.url!r}, description={self.description!r}, "
                f"atoms={self.atoms!r})")
    
class Action:
    def __init__(self, type, input, output, selector, element_id, locator):
        self.type = type
        self.input = input
        self.output = output
        self.selector = selector
        self.element_id = element_id
        self.locator = locator

    def __repr__(self):
        return (f"Action(type={self.type!r}, input={self.input!r}, output={self.output!r}, "
                f"selector={self.selector!r}, element_id={self.element_id!r}, locator={self.locator!r})")
    
class Verb:
    def __init__(self, name, description, src_atom, src_state, dst_atom, dst_state, dst_url, actions):
        self.name = name
        self.description = description
        self.src_atom = src_atom          # Likely an Atom instance or None
        self.src_state = src_state        # Could be None
        self.dst_atom = dst_atom          # Likely an Atom instance or None
        self.dst_state = dst_state        # Likely a State instance or None
        self.dst_url = dst_url            # Could be None
        self.actions = actions            # List of Action instances

    def __repr__(self):
        return (f"Verb(name={self.name!r}, description={self.description!r}, "
                f"src_atom={self.src_atom!r}, src_state={self.src_state!r}, "
                f"dst_atom={self.dst_atom!r}, dst_state={self.dst_state!r}, "
                f"dst_url={self.dst_url!r}, actions={self.actions!r})")
    
class AppGraph:
    def __init__(self, name, description, endpoint, variables, plugins, atoms, states, verbs):
        self.name = name
        self.description = description
        self.endpoint = endpoint
        self.variables = variables
        self.plugins = plugins
        self.atoms = atoms
        self.states = states 
        self.verbs = verbs 

    def __repr__(self):
        return (f"AppGraph(name={self.name!r}, description={self.description!r}, "
                f"endpoint={self.endpoint!r}, variables={self.variables!r}, "
                f"plugins={self.plugins!r}, atoms={self.atoms!r}, states={self.states!r}, verbs={self.verbs!r})")

def variables_constructor(loader, node):
    data = loader.construct_mapping(node)
    return Variables(**data)

def textmarker_constructor(loader, node):
    data = loader.construct_mapping(node)
    return TextMarker(**data)

def atom_constructor(loader, node):
    data = loader.construct_mapping(node)
    return Atom(**data)

def state_constructor(loader, node):
    data = loader.construct_mapping(node)
    return State(**data)

def action_constructor(loader, node):
    data = loader.construct_mapping(node)
    return Action(**data)

def verb_constructor(loader, node):
    data = loader.construct_mapping(node)
    return Verb(**data)

def appgraph_constructor(loader, node):
    data = loader.construct_mapping(node)
    return AppGraph(**data)


class AgentIndex:
    def __init__(self, filename):
        if not os.path.exists(filename):
            raise Exception(f'File {filename} does nopt exist!')
        
        yaml.add_constructor('!yamlable/com.project24.schema.Variables', variables_constructor)
        yaml.add_constructor('!yamlable/com.project24.schema.TextMarker', textmarker_constructor)
        yaml.add_constructor('!yamlable/com.project24.schema.Atom', atom_constructor)
        yaml.add_constructor('!yamlable/com.project24.schema.State', state_constructor)
        yaml.add_constructor('!yamlable/com.project24.schema.Action', action_constructor)
        yaml.add_constructor('!yamlable/com.project24.schema.Verb', verb_constructor)
        yaml.add_constructor('!yamlable/com.project24.schema.AppGraph', appgraph_constructor)

        with open(filename, 'r') as file:
            self.app_graph = yaml.load(file, Loader=yaml.FullLoader)
        self.filename = filename

    def get_verbs(self):
        res = []
        for verb in self.app_graph.verbs:
            res.append(verb.name)
        return res
        

