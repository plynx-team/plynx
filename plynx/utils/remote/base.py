class ContentsHandlerBase(object):
    def __init__(self, remote):
        self.remote = remote

    def get_contents_to_file(self, file_obj):
        raise NotImplementedError()

    def set_contents_from_file(self, file_obj):
        raise NotImplementedError()

    def remove(self):
        raise NotImplementedError()

    def exists(self):
        raise NotImplementedError()


class RemoteBase(object):
    def __init__(self, ContentsHandler, storage_config):
        self.ContentsHandler = ContentsHandler
        self._storage_config = storage_config

    def get_contents_handler(self, path):
        full_path = '{}{}'.format(self._storage_config.prefix, path)
        return self.ContentsHandler(self, full_path)
