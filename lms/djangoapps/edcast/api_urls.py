"""
Custom Edcast APIs that we're putting inside of EDX
"""

from django.conf.urls import patterns, url

from .api_views import UserCourseStatus
from django.conf import settings

urlpatterns = patterns(
    '',
    url(r'^courses_needing_grading$',
        'edcast.api_views.courses_needing_grading', name='courses_needing_grading'),
    url('^course_status_info/{}$'.format(settings.COURSE_ID_PATTERN),
        UserCourseStatus.as_view(),
        name='user_course_status'),
    url(
        r'^course_progress$',
        'edcast.api_views.course_progress', name="course_progress"
    ),
)
