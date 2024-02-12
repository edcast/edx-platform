import pymongo
import os
from .models import HealthCheck
from django.core.cache import cache
from django.conf import settings

import logging
log = logging.getLogger(__name__)

def is_mongo_running():
    """
    Returns True if mongo is running, False otherwise.
    """
    # The mongo command will connect to the service,
    # failing with a non-zero exit code if it cannot connect.
    try:
        store = settings.MODULESTORE['default'].get('OPTIONS', {})
	stores = store.get('stores')
        default = stores[0]
	doc = default.get('DOC_STORE_CONFIG')
        db = doc.get('db')
	string = "mongodb://" + str(doc.get('user')) + ":" + str(doc.get('password')) + \
		"@" + str(doc.get('host')[0]) + ":" + str(doc.get('port')) + "/" + str(doc.get('db'))
        conn = pymongo.MongoClient(string)
        db = conn[db]
        db.test.insert({'aaa': 'aaa'})
        row = db.test.find({'aaa': 'aaa'}).next()['aaa']
        if row != 'aaa':
            raise Exception
        db.test.drop()
        return 'alive'
    except Exception, e:
        log.error('Healthcheck mongo: ' + str(e))
        return 'dead'

def is_memcache_running():
    """
    Returns True if memcache is running, False otherwise.
    """
    # Attempt to set a key in memcache. If we cannot do so because the
    # service is not available, then this will return False.
    try:
        cache.set('cmhealthcheckkey', 'key')
        if (not (cache.get('cmhealthcheckkey') == 'key')):
            raise Exception
        cache.delete('cmhealthcheckkey')
        return 'alive'
    except Exception, e:
        log.error('Healthcheck cache: ', str(e))
        return 'dead'



def is_mysql_running():
    """
    Returns True if mysql is running, False otherwise.
    """
    # We use the MySQL CLI client and capture its stderr
    # If the client cannot connect successfully, stderr will be non-empty
    try:
        test = HealthCheck()
        test.test = "hello"
        test.save()
        test.delete()
        return 'alive'
    except Exception, e:
	log.error('Healthcheck mysql: ', str(e))
        return 'dead'

def check_services():
    status = {}
    status['database'] = is_mysql_running()
    status['mongo'] = is_mongo_running()
    status['memcache'] = is_memcache_running()
    return status
