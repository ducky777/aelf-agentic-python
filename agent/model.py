class AgentModel:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate_response(self, messages: list[dict]) -> str:
        pass
