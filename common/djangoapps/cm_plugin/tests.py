from django.conf import settings
from django.test.client import RequestFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from courseware.access import has_access
if not settings.LMS_TEST_ENV:
    from .views import *
from unittest import skipIf
import json
import hashlib
import yaml

@skipIf(settings.LMS_TEST_ENV, "only invoked from cms")
class EnrollTest(ModuleStoreTestCase):      
    def setUp(self):
        super(EnrollTest, self).setUp()
        self.factory = RequestFactory()
        self.course = CourseFactory.create(org="test",course="courseid", \
            display_name="run1")
        self.user = User.objects.create_user(username='uname', \
            email='user@email.com', password = 'password') 
        self.shared_secret = '123456789'

    def test_user_enrollment(self):
        body = json.dumps({ \
            'email':self.user.email, 'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/enroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_enroll_user(request)
        self.assertEqual(response.status_code,200)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['success'],'ok')
        self.assertFalse(has_access(self.user, 'staff', self.course))

    def test_staff_enrollment(self):
        body = json.dumps({ \
            'email':self.user.email, \
            'role':'staff', \
            'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/enroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_enroll_user(request)
        self.assertEqual(response.status_code,200)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['success'],'ok')
        self.assertTrue(has_access(self.user, 'staff', self.course))
        
    def test_user_enrollment_non_existent_user(self):
        body = json.dumps({ \
            'email':'xx@xx.com', 'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/enroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_enroll_user(request)
        self.assertEqual(response.status_code, 422)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['errors'], 'User does not exist')

    def test_user_enrollment_bad_params(self):
        body = json.dumps({ \
            'email':self.user.email})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/enroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_enroll_user(request)
        self.assertEqual(response.status_code, 400)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['errors'], 'Missing params')
        
        body = json.dumps({ \
            'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/enroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_enroll_user(request)
        self.assertEqual(response.status_code, 400)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['errors'], 'Missing params')

@skipIf(settings.LMS_TEST_ENV, "only invoked from cms")
class UnEnrollTest(ModuleStoreTestCase):
    def setUp(self):
        self.shared_secret = '123456789'
        super(UnEnrollTest, self).setUp()
        self.factory = RequestFactory()
        self.course = CourseFactory.create(org="test",course="courseid", \
            display_name="run1")
        self.user = User.objects.create_user(username='uname', \
            email='user@email.com', password = 'password') 
        course_key = get_key_from_course_id(self.course.id.to_deprecated_string())
        CourseEnrollment.enroll(self.user, course_key)

    def test_user_unenrollment(self):
        body = json.dumps({ \
            'email':self.user.email, 'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/unenroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_unenroll_user(request)
        self.assertEqual(response.status_code,200)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['success'],'ok')

    def test_staff_unenrollment(self):
        body = json.dumps({ \
            'email':self.user.email, \
            'role':'staff', \
            'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/enroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_unenroll_user(request)
        self.assertEqual(response.status_code,200)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['success'],'ok')
        self.assertFalse(has_access(self.user, 'staff', self.course))

    def test_user_unenrollment_bad_params(self):
        body = json.dumps({ \
            'email':self.user.email})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/unenroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_unenroll_user(request)
        self.assertEqual(response.status_code, 400)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['errors'],'Missing params')
        body = json.dumps({ \
            'course_id':self.course.id.to_deprecated_string()})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/unenroll', \
            body, \
            content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_unenroll_user(request)
        self.assertEqual(response.status_code, 400)
        response_object = json.loads(response.content)
        self.assertEqual(response_object['errors'],'Missing params')

@skipIf(settings.LMS_TEST_ENV, "only invoked from cms")
class UserCreationTest(ModuleStoreTestCase):    
    def setUp(self):
        super(UserCreationTest, self).setUp()
        self.shared_secret = '123456789'        
        self.factory = RequestFactory()
        self.user_creation_options = {'username':'uname', \
              'email':'email@email.com', \
              'password':'pwd123!123', \
              'name':'name'}

    def test_user_creation(self):
        body = json.dumps({ \
            'name':'name','email':'email@email.com', \
                'username':'uname','password':'pwd123!123'})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/user', \
                body, content_type='application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_create_new_user(request)
        self.assertEqual(response.status_code, 200)
        response_object = json.loads(response.content)
        self.assertTrue('email@email.com' in response_object['id'])

    def test_bad_params_user_error(self):
        body = json.dumps({ \
            'username':'uname','email':'email@email.com', \
                'password':'password'})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/user', \
            body, content_type='application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_create_new_user(request)
        self.assertEqual(response.status_code, 400)
        response_object = json.loads(response.content)
        self.assertTrue('Bad Request' in response_object['errors'])

    def test_duplicate_email_user_error(self):
        body = json.dumps({ \
            'name':'name','email':'email@email.com', \
                'username':'uname','password':'pwd123!123'})
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post('/cm/user', \
                body, \
                content_type = 'application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        first_response = cm_create_new_user(request)

        # again
        response = cm_create_new_user(request)
        self.assertEqual(response.status_code, 200)
        response_object = json.loads(response.content)
        print response_object
        self.assertTrue(('email@email.com') in response_object['id'])

@skipIf(settings.LMS_TEST_ENV, "only invoked from cms")
class CourseDeletionTest(ModuleStoreTestCase):
    def setUp(self):
        self.shared_secret = '123456789'
        super(CourseDeletionTest, self).setUp()
        self.factory = RequestFactory()
        
    def test_deleting_course(self):
        course = CourseFactory.create(org="test",course="courseid", \
                                           display_name="run1")
        course_id = course.id
        user = User.objects.create_user(username='uname', \
                                             email='user@email.com', password = 'password')
        CourseInstructorRole(course.id).add_users(user)
        course_deletion_options = {'email': user.email}
        body = json.dumps(course_deletion_options)
        token = hashlib.sha256(self.shared_secret + "|" + body)                                       
        url = '/cm/delete_course/' + str(course.id)
        request = self.factory.post(url, body,
                                    content_type='application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_course_delete(request, str(course_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), u'{"message": "successfully deleted course"}')


    def test_deleting_non_existent_course(self):
        url = '/cm/delete_course/'
        user = User.objects.create_user(username='uname', \
                                            email='someuser@mail.com', password = 'password')
        course_deletion_options = {'email': 'someuser@mail.com'}
        body = json.dumps(course_deletion_options)
        token = hashlib.sha256(self.shared_secret + "|" + body)
        request = self.factory.post(url + "1", body , content_type='application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_course_delete(request, "1")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content), u'{"error": "Course Key not found for course id: 1"}')

    def test_deletion_by_non_instructor(self):
        course = CourseFactory.create(org="test",course="courseid", \
                                      display_name="run1")
        course_id = course.id
        user = User.objects.create_user(username='uname', \
                                        email='user1@email.com', password = 'password')

        course_deletion_options = {'email': user.email}
        body = json.dumps(course_deletion_options)
        token = hashlib.sha256(self.shared_secret + "|" + body)
        url = '/cm/delete_course/' + str(course.id)
        request = self.factory.post(url, body, content_type='application/json',HTTP_X_SAVANNAH_TOKEN = token.hexdigest())
        response = cm_course_delete(request, str(course_id))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content), u'{"error": "course deletion attempted by unauthorized user"}')