import os 

from azure.ai.inference import ChatCompletionsClient
from azure.identity import DefaultAzureCredential, ChainedTokenCredential, AzureCliCredential

class Agent:
    def __init__(
            self,
            api_version = '2025-03-01-preview',  # Ensure this is a valid API version see: https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
            model_name = 'gpt-4.1',  # Ensure this is a valid model name
            model_version = '2025-04-14',  # Ensure this is a valid model version
            deployment_name = "gpt-4.1_2025-04-14", #re.sub(r'[^a-zA-Z0-9-_]', '', f'{model_name}_{model_version}')  # If your Endpoint doesn't have harmonized deployment names, you can use the deployment name directly: see: https://aka.ms/trapi/models
    ):
        
        # api_version = '2025-03-01-preview',  # Ensure this is a valid API version see: https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
        # model_name = 'gpt-4o',  # Ensure this is a valid model name
        # model_version = '2024-11-20',  # Ensure this is a valid model version
        # deployment_name = "gpt-4o_2024-11-20", #re.sub(r'[^a-zA-Z0-9-_]', '', f'{model_name}_{model_version}')  # If your Endpoint doesn't have harmonized deployment names, you can use the deployment name directly: see: https://aka.ms/trapi/models

        self.credential = ChainedTokenCredential(
            AzureCliCredential(),
            DefaultAzureCredential(
                exclude_cli_credential=True,
                # Exclude other credentials we are not interested in.
                exclude_environment_credential=True,
                exclude_shared_token_cache_credential=True,
                exclude_developer_cli_credential=True,
                exclude_powershell_credential=True,
                exclude_interactive_browser_credential=True,
                exclude_visual_studio_code_credentials=True,
                # DEFAULT_IDENTITY_CLIENT_ID is a variable exposed in
                # Azure ML Compute jobs that has the client id of the
                # user-assigned managed identity in it.
                # See https://learn.microsoft.com/en-us/azure/machine-learning/how-to-identity-based-service-authentication#compute-cluster
                # In case it is not set the ManagedIdentityCredential will
                # default to using the system-assigned managed identity, if any.
                managed_identity_client_id=os.environ.get("DEFAULT_IDENTITY_CLIENT_ID"),
            )
        )
        self.scopes = ["api://trapi/.default"]

        # Note: Check out the other model deployments here - https://dev.azure.com/msresearch/TRAPI/_wiki/wikis/TRAPI.wiki/15124/Deployment-Model-Information
        self.api_version = api_version
        self.model_name = model_name
        self.model_version = model_version
        self.deployment_name = deployment_name
        self.instance = "redmond/interactive/openai" #'gcr/shared/openai' # See https://aka.ms/trapi/models for the instance name
        self.endpoint = f'https://trapi.research.microsoft.com/{self.instance}/deployments/'+self.deployment_name

        self.llm_client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=self.credential,
            credential_scopes=self.scopes,
            api_version=self.api_version
        )