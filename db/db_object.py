from abc import ABCMeta, abstractmethod


class DBObject(object):

    _dirty = True

    @abstractmethod
    def save(self):
        pass

    @abstractmethod
    def load(self):
        pass

    def is_dirty(self):
        return self._dirty

    def __setattr__(self, key, value):
        self.__dict__['_dirty'] = True
        self.__dict__[key] = value
