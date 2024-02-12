import functools

from django.views.decorators.cache import cache_control
from .authentication import RestSessionAuthentication

from util.json_request import JsonResponse
from django.db import connection
from datetime import datetime

from django.core.exceptions import ValidationError
from opaque_keys.edx.keys import UsageKey, CourseKey
from opaque_keys import InvalidKeyError
from django.utils import dateparse
from rest_framework import views
from lms.djangoapps.courseware.model_data import FieldDataCache
from lms.djangoapps.courseware.module_render import get_module_for_descriptor
from lms.djangoapps.courseware.views import get_current_child, save_positions_recursively_up
from lms.djangoapps.courseware.courses import get_course
from lms.djangoapps.courseware.courseware_access_exception import CoursewareAccessException
from lms.djangoapps.course_blocks.api import get_course_blocks

from rest_framework import status, response
from rest_framework.response import Response
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from xblock.fields import Scope
from xblock.runtime import KeyValueStore
from mobile_api import errors

@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def courses_needing_grading(request):
    cursor = connection.cursor()

    try:
        last_update = request.GET.get('last_update', None)
        if last_update is None:
            return JsonResponse({'error': 'Last update time not passed'}, 400)
        else:
            last_update = int(last_update)
    except ValueError:
        return JsonResponse({'error': 'Invalid update time passed'}, 400)

    last_update_datetime = datetime.utcfromtimestamp(last_update)
    last_update_sql = last_update_datetime.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("SELECT DISTINCT(course_id) FROM courseware_studentmodule WHERE max_grade IS NOT NULL AND modified > %s", [last_update_sql])
    response = cursor.fetchall()

    data = [col[0] for col in response]

    return JsonResponse({
        'last_update': last_update,
        'last_update_sql': last_update_sql,
        'courses': data
    }, status = 200)


def load_course_data(depth=0):
    """
    Method decorator for an API endpoint that verifies the user has access to the course.
    """
    def _decorator(func):
        """Outer method decorator."""
        @functools.wraps(func)
        def _wrapper(self, request, *args, **kwargs):
            """
            Expects kwargs to contain 'course_id'.
            Passes the course descriptor to the given decorated function.
            Raises 404 if access to course is disallowed.
            """
            course_id = CourseKey.from_string(kwargs.pop('course_id'))
            with modulestore().bulk_operations(course_id):
                try:
                    course = get_course(course_id, depth=depth)
                except CoursewareAccessException as error:
                    return response.Response(data=error.to_json(), status=status.HTTP_404_NOT_FOUND)
                return func(self, request, course=course, *args, **kwargs)
        return _wrapper
    return _decorator


class UserCourseStatus(views.APIView):
    authentication_classes = (RestSessionAuthentication, )

    """
    **Use Cases**

        Get or update the ID of the module that the specified user last
        visited in the specified course.

    **Example Requests**

        GET /edcast/api/course_status_info/{course_id}

        PATCH /edcast/api/course_status_info/{course_id}

        **PATCH Parameters**

          The body of the PATCH request can include the following parameters.

          * last_visited_module_id={module_id}
          * modification_date={date}

            The modification_date parameter is optional. If it is present, the
            update will only take effect if the modification_date in the
            request is later than the modification_date saved on the server.

    **Response Values**

        If the request is successful, the request returns an HTTP 200 "OK" response.

        The HTTP 200 response has the following values.

        * last_visited_module_id: The ID of the last module that the user
          visited in the course.
        * last_visited_module_path: The ID of the modules in the path from the
          last visited module to the course module.
    """

    http_method_names = ["get", "patch"]

    def _last_visited_module_path(self, request, course):
        """
        Returns the path from the last module visited by the current user in the given course up to
        the course module. If there is no such visit, the first item deep enough down the course
        tree is used.
        """
        field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            course.id, request.user, course, depth=2)

        course_module = get_module_for_descriptor(
            request.user, request, course, field_data_cache, course.id, course=course
        )

        path = [course_module]
        chapter = get_current_child(course_module, min_depth=2)
        if chapter is not None:
            path.append(chapter)
            section = get_current_child(chapter, min_depth=1)
            if section is not None:
                path.append(section)

        path.reverse()
        return path

    def _get_course_info(self, request, course):
        """
        Returns the course status
        """
        path = self._last_visited_module_path(request, course)
        path_ids = [unicode(module.location) for module in path]
        return Response({
            "last_visited_module_id": path_ids[0],
            "last_visited_module_path": path_ids,
        })

    def _update_last_visited_module_id(self, request, course, module_key, modification_date):
        """
        Saves the module id if the found modification_date is less recent than the passed modification date
        """
        field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            course.id, request.user, course, depth=2)
        try:
            module_descriptor = modulestore().get_item(module_key)
        except ItemNotFoundError:
            return Response(errors.ERROR_INVALID_MODULE_ID, status=400)
        module = get_module_for_descriptor(
            request.user, request, module_descriptor, field_data_cache, course.id, course=course
        )

        if modification_date:
            key = KeyValueStore.Key(
                scope=Scope.user_state,
                user_id=request.user.id,
                block_scope_id=course.location,
                field_name='position'
            )
            original_store_date = field_data_cache.last_modified(key)
            if original_store_date is not None and modification_date < original_store_date:
                # old modification date so skip update
                return self._get_course_info(request, course)

        save_positions_recursively_up(request.user, request, field_data_cache, module, course=course)
        return self._get_course_info(request, course)

    @load_course_data(depth=0)
    def get(self, request, course, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Get the ID of the module that the specified user last visited in the specified course.
        """

        return self._get_course_info(request, course)

    @load_course_data(depth=0)
    def patch(self, request, course, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Update the ID of the module that the specified user last visited in the specified course.
        """
        module_id = request.data.get("last_visited_module_id")
        modification_date_string = request.data.get("modification_date")
        modification_date = None
        if modification_date_string:
            modification_date = dateparse.parse_datetime(modification_date_string)
            if not modification_date or not modification_date.tzinfo:
                return Response(errors.ERROR_INVALID_MODIFICATION_DATE, status=400)

        if module_id:
            try:
                module_key = UsageKey.from_string(module_id)
            except InvalidKeyError:
                return Response(errors.ERROR_INVALID_MODULE_ID, status=400)

            return self._update_last_visited_module_id(request, course, module_key, modification_date)
        else:
            # The arguments are optional, so if there's no argument just succeed
            return self._get_course_info(request, course)


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def course_progress(request):
    course_key_string = request.GET.get('course_id', None)
    if not course_key_string:
        raise ValidationError('course_id is required.')
    try:
        course_key = CourseKey.from_string(course_key_string)
        course_usage_key = modulestore().make_course_usage_key(course_key)
    except InvalidKeyError:
        raise ValidationError("'{}' is not a valid course key.".format(unicode(course_key_string)))

    username = request.GET.get('username', None)
    if not username:
        raise ValidationError('username is required.')

    blocks = get_course_blocks(
        request.user,
        course_usage_key,
        transformers=[],
    )
    blocks_data = blocks._block_data_map

    # Get current count
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(courseware_studentmodule.id) FROM courseware_studentmodule" +
                   " LEFT JOIN auth_user ON courseware_studentmodule.student_id = auth_user.id" +
                   " WHERE courseware_studentmodule.course_id = %s" +
                   " AND courseware_studentmodule.module_type = 'sequential'" +
                   " AND auth_user.username = %s", [course_key_string, username])
    completion_length = cursor.fetchone()[0]

    # Data
    course_length = len([k for k, v in blocks_data.iteritems() if v.xblock_fields['category'] == 'sequential'])
    if course_length <= 0:
        course_length = 1

    completion_percentage = int((float(completion_length) / course_length) * 100)

    return JsonResponse({'course_length': course_length,
                         'completion_length': completion_length,
                         'completion_percentage': completion_percentage})
