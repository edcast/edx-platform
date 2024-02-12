from django.conf.urls import patterns, url
from .views import *

urlpatterns = patterns('',
    url(r'^cm/user/$', cm_create_new_user),
    url(r'^cm/enroll/$', cm_enroll_user),
    url(r'^cm/unenroll/$', cm_unenroll_user),
    url(r'^cm/set_cookie/$', set_cookie),
    url(r'^cm/healthcheck/$', healthcheck),
    url(r'^cm/delete_course/(/)?(?P<course_id>.+)?$', cm_course_delete),
    )
