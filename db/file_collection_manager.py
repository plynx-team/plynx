from . import File
from utils.common import to_object_id
from utils.db_connector import *

class FileCollectionManager(object):
    """
    """

    @staticmethod
    def get_db_files(author, status=None, per_page=20, offset=0):
        if status and isinstance(status, basestring):
            status = [status]
        if not status:
            db_files = db.files.find({
                '$or': [
                    {'author': author},
                    {'public': True}
                ]
                }).sort('insertion_date', -1).skip(offset).limit(per_page)
        else:
            db_files = db.files.find({
                '$and': [{
                    '$or': [
                            {'author': author},
                            {'public': True}
                        ]
                    },
                    {'file_status': {'$in': status}}
                    ]
                }).sort('insertion_date', -1).skip(offset).limit(per_page)

        res = []
        for file in db_files:
            file['_readonly'] = (author != to_object_id(file['author']))
            res.append(file)
        return res

    @staticmethod
    def get_db_files_count(author, status=None):
        if status and isinstance(status, basestring):
            status = [status]
        if not status:
            return db.files.count({
                '$or': [
                    {'author': author},
                    {'public': True}
                ]
                })
        else:
            return db.files.count({
                '$and': [{
                    '$or': [
                            {'author': author},
                            {'public': True}
                        ]
                    },
                    {'file_status': {'$in': status}}
                    ]
                })

    @staticmethod
    def get_db_file(file_id, author):
        res = db.files.find_one({'_id': to_object_id(file_id)})
        res['_readonly'] = (author != to_object_id(res['author']))
        return res
