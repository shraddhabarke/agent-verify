import json
import os 
class Intents:
    def __init__(self, filename = r'C:\Users\t-avalsingh\WebVoyager\data\WebVoyager_data.jsonl'):
        if not os.path.exists(filename):
            raise Exception(f'File {filename} does not exist!')
        self.filename = filename 

        with open(self.filename, 'r') as f:
            self.intents = []
            for i, line in enumerate(f):
                self.intents.append(json.loads(line))
            
    def loc(self, i):
        return self.intents[i]['ques']
    
    def filter(self, fields, values):
        delete_indices = []
        for i in range(len(self.intents)):
            for field, value in zip(fields, values):
                if self.intents[i][field] != value:
                    delete_indices.append(i)

        for i in range(len(delete_indices)):
            del self.intents[delete_indices[len(delete_indices)-i-1]]