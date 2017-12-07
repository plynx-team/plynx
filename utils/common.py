from bson.objectid import ObjectId

def to_object_id(_id):
    if type(_id) != ObjectId:
        _id = ObjectId(_id)
    return _id
