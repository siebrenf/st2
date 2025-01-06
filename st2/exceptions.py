class GameError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class ServerResetError(Exception):
    pass


class ExtractDestabilizedError(Exception):
    def __init__(self, *args):
        super().__init__(*args)
