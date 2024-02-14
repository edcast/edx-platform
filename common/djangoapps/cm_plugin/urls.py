from django.urls import path, re_path
from .views import (
    cm_create_new_user,
    cm_enroll_user,
    cm_unenroll_user,
    set_cookie,
    healthcheck,
    cm_course_delete
)

urlpatterns = [
    path('cm/user/', cm_create_new_user),
    path('cm/enroll/', cm_enroll_user),
    path('cm/unenroll/', cm_unenroll_user),
    path('cm/set_cookie/', set_cookie),
    path('cm/healthcheck/', healthcheck),
    re_path(r'^cm/delete_course/(/)?(?P<course_id>.+)?$', cm_course_delete),
]