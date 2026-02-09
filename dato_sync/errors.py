class BadConfigurationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"Bad configuration of the dato_sync plugin: {self.message}"