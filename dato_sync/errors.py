class BadConfigurationError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"Bad configuration of the dato_sync plugin: {self.message}"


class IllegalSyncOptionsError(Exception):
    def __init__(self, model: object, options_type: object, message: str):
        self.model = model
        self.options_type = options_type
        self.message = message

    def __str__(self):
        return f"The sync options provided for {self.model} in {self.options_type} are illegal: {self.message}"