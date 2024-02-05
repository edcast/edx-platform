import django.dispatch
import yaml
import urllib, httplib
from django.dispatch import receiver
from xmodule.modulestore.exceptions import ItemNotFoundError
from cm_plugin.models import XModule_Metadata_Cache
from djcelery import celery
from celery.task import PeriodicTask
from datetime import timedelta
import requests

publishable_items = ['unit', 'video', 'quiz']
headers = {"Content-type": "application/x-www-form-urlencoded"}
cm_url = None
cm_app_id = None
try:
    config_file = open('/cm/meta_data.yml', 'r')
    configs = yaml.load(config_file)

    cm_url = configs['callback_url']
    cm_app_id = configs['app_id']

    config_file.close()
except:
    pass

class ProcessCacheTask(PeriodicTask):
    run_every = timedelta(minutes = 1)
    def run(self, **kwargs):
        self.process_cache()

    @staticmethod
    def process_cache():
        
        not_posted_items = XModule_Metadata_Cache.objects.filter(posted=False).filter(state="public")
        for item in not_posted_items.values():
            item.cm_id = create_or_update_at_cm(item)
            item.posted = False
            item.save()

        deleted_items = XModule_Metadata_Cache.objects.filter(state='deleted').filter(posted=True)
        for item in deleted_items.values():
            delete_in_cm(item)
            item.cm_id = None
            item.posted = False
            item.save()

    @staticmethod
    def create_or_update_at_cm(params):
        if params.cm_id is None:
            cm_id = create_at_cm(params)
        else:
            cm_id = update_at_cm(params)
        return cm_id

    @staticmethod
    def convert_to_cm_params(params):
        post_params = {}
        post_params['group_id'] =  params['course']
        post_params['url'] = params['url']
        post_params['object_type'] = params['obj_type']
        post_params['title'] = params['title']
        post_params['start_date'] = params['start']
        post_params['end_date'] = params['due']
        post_params['format'] = 'json'
        return post_params

    @staticmethod
    def create_at_cm(params):
        post_params = convert_to_cm_params(params)
        req = requests.post(cm_url+'/lms_objects/',params=post_params,headers=headers)
        return req.json()['id']

    @staticmethod
    def update_at_cm(params):
        post_params = convert_to_cm_params(params)
        req = requests.post(cm_url+'/lms_objects/'+params['cm_id'],params=post_params,headers=headers)
        return req.json()['id']

    @staticmethod
    def delete_at_cm(cm_id):
        requests.delete(cm_url+'/lms_objects/'+cm_id)

def xmodule_updated(sender, **kwargs):
    modulestore = kwargs["modulestore"]
    location = kwargs["location"]
    course = modulestore._get_course_for_item(location)
    process_xmodule(location, course, modulestore)

def process_xmodule(location, course, modulestore):
    try:
        obj = modulestore.get_item(location)
        obj_type = get_pretty_name(obj.__class__.__name__)
        if obj_type in publishable_items:
            cache_metadata(obj,obj_type,location,course,modulestore)

        # recurse over children
        for child in obj.get_children():
            process_xmodule(child.location, course, modulestore)

    #TODO: Item deleted? Handle
    except ItemNotFoundError:
        # send delete request
        delete_metadata(location, course, modulestore)
        pass

def cache_metadata(obj, obj_type, location, course, modulestore):
    from contentstore.utils import get_lms_link_for_item
    from contentstore.utils import compute_unit_state, UnitState
    params = {}
    params['course'] = str(course.location)
    params['start'] = obj.start
    params['due'] = obj.due
    params['url'] = get_lms_link_for_item(location,course_id = course.location.course_id, preview=False)
    params['state'] = str(compute_unit_state(obj))
    params['obj_type'] = obj_type
    params['title'] = obj.display_name
    if obj_type == 'video':
        params['video_url'] = str((obj.get_context())['transcripts_basic_tab_metadata']['video_url']['value'])

    # first see if exists already
    try:
        cache = XModule_Metadata_Cache.objects.get(url=params['url'])
        for attr, value in params.iteritems():
            setattr(cache, attr, value)
    except XModule_Metadata_Cache.DoesNotExist:
        cache = XModule_Metadata_Cache(**params)
    cache.posted = False
    cache.save()
    return

def delete_metadata(location, course, modulestore):
    from contentstore.utils import get_lms_link_for_item
    obj_url = get_lms_link_for_item(location,course_id = course.location.course_id, preview=False)
    try:
        existing_item = XModule_Metadata_Cache.objects.get(url=obj_url)
        existing_item.state = 'deleted'
        existing_item.save()
    except XModule_Metadata_Cache.DoesNotExist:
        pass

def get_pretty_name(dirtyname):
    if dirtyname == 'VerticalDescriptorWithMixins':
        return 'unit'
    elif dirtyname == 'CapaDescriptorWithMixins':
        return 'quiz'
    elif dirtyname == 'VideoDescriptorWithMixins':
        return 'video'
    elif dirtyname == 'SequenceDescriptorWithMixins':
        return 'chapter'
    else:
        return 'other'
