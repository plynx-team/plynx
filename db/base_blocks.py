from utils.db_connector import *

def get_base_blocks():
    return list(db.base_blocks.find())
