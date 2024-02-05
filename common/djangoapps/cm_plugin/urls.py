from django.urls import path
from .views import *

urlpatterns = [
    # path('cm/user/', cm_create_new_user),
    # path('cm/enroll/', cm_enroll_user),
    # path('cm/unenroll/', cm_unenroll_user),
    # path('cm/set_cookie/', set_cookie),
    path('cm/healthcheck/', healthcheck),
    # path('cm/delete_course/<course_id>/', cm_course_delete),
]