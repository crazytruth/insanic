class AnonymousUser(dict):

    def __init__(self):
        super().__init__(id=None, is_staff=False, email=None)

    def __str__(self):
        return 'AnonymousUser'
