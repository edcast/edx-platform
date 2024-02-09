import json
import logging
from urllib.parse import urlparse, unquote

from django.conf import settings
from django.contrib.auth.models import User
from django.db import DatabaseError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from common.djangoapps.student import auth
from common.djangoapps.student.helpers import do_create_account, AccountValidationError
from common.djangoapps.student.models import CourseEnrollment, CourseAccessRole
from common.djangoapps.student.roles import CourseInstructorRole
from common.djangoapps.student.tests.factories import AdminFactory
from common.djangoapps.util.json_request import expect_json
from openedx.core.djangoapps.user_authn.views.registration_form import AccountCreationForm
from lms.djangoapps.courseware.models import StudentModule
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from cms.djangoapps.contentstore.utils import delete_course
from cms.djangoapps.contentstore.views.user import CannotOrphanCourse, try_remove_instructor
from .healthcheck import check_services
from .token import validate_token

log = logging.getLogger(__name__)

# Create your views here.
def get_key_from_course_id(course_id):
    return CourseKey.from_string(course_id)

"""
Enroll user in course. 
params:
    email => the user to enroll
    course_id => the course to enroll in

    NOTE: returns status :ok if course_id invalid
"""

@csrf_exempt
@expect_json
def cm_enroll_user(request):
    response_format = request.GET.get('format','html')
    if response_format == 'json' or 'application/json' in request.META.get('HTTP/ACCEPT', 'application/json'):
        if request.method == 'POST':
            if validate_token(request.body, request) is False:
                return HttpResponse('Unauthorized', status=401)
            log.info(f"Request Json : {request.json}")
            if 'username' not in request.json or 'email' not in request.json or 'course_id' not in request.json:
                return HttpResponse(content=json.dumps({'errors':'Missing params'}), \
                        content_type = 'application/json', status=400)
            try:
                log.info("Enrolling user: " + request.json.get('email') + "username: " + request.json.get('username') + " course: " + request.json.get('course_id'))
                enroll_user = User.objects.get(username=request.json.get('username'))
                CourseEnrollment.enroll(enroll_user, \
                                                 get_key_from_course_id(request.json.get('course_id')))

                # See if enrolling with staff credentials
                if request.json.get('role') == 'staff':
                    global_admin = AdminFactory()
                    course = get_key_from_course_id(request.json.get('course_id'))
                    auth.add_users(global_admin, CourseInstructorRole(course), User.objects.get(username=request.json.get('username')))
                    
                content = {'success':'ok'}
                status_code = 200
            except User.DoesNotExist:
                content = {'errors':'User does not exist'}
                status_code = 422
            return HttpResponse(content=json.dumps(content), status=status_code, \
                    content_type = 'application/json')
        else:
            return HttpResponse(content=json.dumps({}), status=404, content_type = 'application/json')
    else:
        return HttpResponse(content=json.dumps({}), status=404, content_type = 'application/json')

"""
UnEnroll user in course. 
params:
    email => the user to unenroll
    course_id => the course to unenroll in

    NOTE: returns status :ok even if either email or course_id is invalid
"""

@csrf_exempt
@expect_json
def cm_unenroll_user(request):
    """
    This is a hard unenroll as opposed to the regular soft unenroll that edx uses internally.
    """
    response_format = request.GET.get('format','html')
    if response_format == 'json' or 'application/json' in request.META.get('HTTP/ACCEPT', 'application/json'):
        if request.method == 'POST':
            if validate_token(request.body, request) is False:
                log.warn(f"Unauthorized access made by course: {request.json.get('email')}, user: {request.json.get('course_id')}")
                return HttpResponse('Unauthorized', status=401)
            if 'username' not in request.json or 'email' not in request.json or 'course_id' not in request.json:
                log.error("Incomplete request.")
                return HttpResponse(content=json.dumps({'errors':'Missing params'}), \
                        content_type = 'application/json', status=400)

            try:
                log.info(f"Unenrolling user: {request.json.get('email')} ({request.json.get('username')}) from course: {request.json.get('course_id')}")
                user = User.objects.get(username=request.json.get('username'))
                request.user = user
            except User.DoesNotExist:
                log.info(f"Unknown user : {request.json.get('email')} ({request.json.get('username')}) from course {request.json.get('course_id')}")
                return HttpResponse(content=json.dumps({'errors': 'Unknown user'}), status=500, content_type='application/json')
            course_id = request.json.get('course_id')

            #locator = loc_mapper().translate_location(course_id, CourseDescriptor.id_to_location(course_id))

            role = request.json.get('role')
            if role == 'staff':
                try:
                    try_remove_instructor(request, get_key_from_course_id(course_id), user)
                    log.info(f"staff unenrolled: {str(user)}")
                except CannotOrphanCourse as oops:
                    log.warn(f"last course admin removal attempted: {str(user)}")
                    return HttpResponse(content=json.dumps(oops.msg), status=400, content_type='application/json')
            else:
                log.info(f"student unenroll: {str(user)}")
                try:
                    CourseEnrollment.unenroll(user, get_key_from_course_id(request.json.get('course_id')))
                    status_code = 200
                except DatabaseError:
                    # this is just for tests. This error will never be hit in production
                    # should probably consider moving cm_plugin out of common too.
                    log.error(f"Unenroll failed for user: {request.json.get('email')} ({request.json.get('username')}) from course: {request.json.get('course_id')}")
                    pass

            status_code = 200
            content = {'success':'ok'}

            log.info(f"Unenrolled user: {request.json.get('email')} ({request.json.get('username')}) from course: {request.json.get('course_id')}")
            return HttpResponse(content=json.dumps(content), status=status_code, content_type='application/json')
        else:
            return HttpResponse(content=json.dumps({}), status=404, content_type='application/json')
    else:
        return HttpResponse(content=json.dumps({}), status=404, content_type='application/json')


"""
POST request from cm to create new user.
Returns unique id (email, username)
"""
@csrf_exempt
@expect_json
def cm_create_new_user(request):
    response_format = request.GET.get('format','html')
    if response_format == 'json' or 'application/json' in request.META.get('HTTP/ACCEPT','application/json'):
        if request.method == 'POST':
            if validate_token(request.body, request) is False:
                return HttpResponse('Unauthorized', status=401)
            try:
                form = AccountCreationForm(
                        data=request.json,
                        tos_required=False
                    )
                ret = do_create_account(form)
                if isinstance(ret, HttpResponse):
                    response_body = json.loads(ret.content)
                    content = {'errors':response_body['value']}
                    status_code = 422
                elif isinstance(ret, tuple):
                    created_user = User.objects.get(username=ret[0].username)
                    created_user.is_active = True
                    created_user.save()
                    content = {'id':ret[0].email, 'username': ret[0].username}
                    status_code = 200
            except AccountValidationError:
                    user = User.objects.get(username=request.json.get('username'))
                    content = {'id': user.email, 'username': user.username}
                    status_code = 200
            except:
                    content = {'errors':'Bad Request'}
                    status_code = 400

            return HttpResponse(content = json.dumps(content), \
                    content_type = 'application/json', \
                    status = status_code)
        else:
            return HttpResponse(content=json.dumps({}), status=404, content_type='application/json')
    else:
        return HttpResponse(content=json.dumps({}), status=404, content_type='application/json')

def set_cookie(request):
    referrer = request.GET.get('return_to_url')

    allowed_domains = settings.ALLOWED_DOMAINS
    if not allowed_domains:
        allowed_domains = ['edcast.me', 'edcastcloud.com', 'cmappstage.com']

    if not is_edcast_url(referrer, allowed_domains):
        return JsonResponse({"error": "invalid url"}, status=404)

    response = render(request, 'cm_plugin/cookie.html', {"referrer":unquote(referrer)})
    response.set_cookie(key='visited', value='true')

    return response

def is_edcast_url(url, allowed_domains):
    if url is not None:
        parsed_uri = urlparse(url)
    else:
        return False

    if parsed_uri.scheme is None or (parsed_uri.scheme is not None and (parsed_uri.scheme not in ['http', 'https'])):
        return False

    domain = parsed_uri.netloc
    if domain is not None and (domain in allowed_domains):
        return True
    else:
        for allowed_domain in allowed_domains:
            if '*' in allowed_domain and domain.endswith(allowed_domain.replace('*.', '')):
                return True

    return False

def healthcheck(request):
    if request.GET.get('all', False):
        result = check_services()
    else:
        result = {'status': 'alive'}

    return HttpResponse(content=json.dumps(result), status=200, content_type="application/json")


@csrf_exempt
@expect_json    
def cm_course_delete(request, course_id=None):
    response_format = request.GET.get('format', 'html')
    if response_format == 'json' or 'application/json' in request.META.get('HTTP/ACCEPT', 'application/json'):
        if request.method == 'POST':
            if not validate_token(request.body, request):
                log.warning(f"Unauthorized access made by course: {course_id}, user: {request.json.get('email')} ({request.json.get('username')})" )
                return HttpResponse('Unauthorized', status=401)

            email = request.json.get('email')
            username = request.json.get('username')
            try:
                instructor = User.objects.get(username=username)
                request.user = instructor
            except User.DoesNotExist:
                log.error(f"course deletion attempted by unregistered user: {email} ({username})")
                return JsonResponse({'error': 'course deletion attempted by unregistered user'}, status=400)

            if course_id is None:
                return JsonResponse({'error': 'Course ID does not exist'}, status=404)

            try:
                course_key = CourseKey.from_string(course_id)
            except InvalidKeyError:
                try:
                    course_key = SlashSeparatedCourseKey.from_string(course_id)
                except InvalidKeyError:
                    course_key = None

            if course_key is None:
                return JsonResponse({'error': 'Course Key not found for course id: ' + str(course_id)}, status=404)

            if not auth.user_has_role(instructor, CourseInstructorRole(course_key)):
                log.error(f"course deletion attempted by unauthorized user: {email} ({username})")
                return JsonResponse({'error': 'course deletion attempted by unauthorized user'}, status=401)

            try:
                delete_course(course_key, instructor.id)
                try:
                    with transaction.atomic():
                        StudentModule.objects.filter(course_id=course_key).delete()
                except:
                    # We need this for testing. The above mentioned model lives in
                    # LMS but our tests are executed via CMS. This piece of code
                    # makes sure that the test safely skips over this and runs
                    # successfully.
                    pass

                try:
                    with transaction.atomic():
                        CourseEnrollment.objects.filter(course_id=course_key).delete()
                except Exception as e:
                    pass
                try:
                    with transaction.atomic():
                        CourseAccessRole.objects.get(course_id=course_key).delete()
                except CourseAccessRole.DoesNotExist:
                    pass
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)

            return JsonResponse({'message': "successfully deleted course"}, status=200)
        else:
            return JsonResponse({}, status=404)
    else:
        return JsonResponse({}, status=404)