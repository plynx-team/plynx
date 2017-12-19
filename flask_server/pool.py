#!/usr/bin/env python
from flask_server.common import *
from flask_server.send_file import *
import utils.pool_collection as pcoll
import utils.model_collection as mcoll
import utils.img_collection as icoll
from utils.common import toObjectID
from collections import defaultdict, OrderedDict
import random


SAMPLE_SIZE=10

@app.route("/pools/<pool_id>")
def get_pool(pool_id):
    pool_id = toObjectID(pool_id)
    src_images = pcoll.getSampleOfImages(pool_id, 1000, previewOnly=True)
    class_images = defaultdict(list)
    neg_images = []
    for img in src_images:
        if 'valid_image' not in img or not img['valid_image']:
            continue
        #pos_images.append(img)
        pool_info = [p for p in img['pools'] if p['poolId'] == pool_id][0]
        class_images[pool_info['target']].append(img)

    targets = class_images.keys()
    for k in targets:
        class_len = len(class_images[k])
        class_images[k] = random.sample(class_images[k], min(SAMPLE_SIZE, class_len))

    models = list(mcoll.getModelsByPoolId(pool_id))
    pool = pcoll.getPool(pool_id)[0]

    properties = OrderedDict()
    properties['Pool Size'] = pcoll.getPoolSize(pool_id)
    properties['Pool Size (Valid images)'] = pcoll.getPoolSize(pool_id, valid_only=True)
    properties['Created'] = pool['date_inserted']
    properties['Targets'] = ', '.join(map(str, class_images.keys()))

    app.logger.info(models)
    return render_template('pool.html', pool=pool, class_images=class_images, models=models, properties=properties)
