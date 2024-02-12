from django.db import models

class XModule_Metadata_Cache(models.Model):
    url = models.CharField(max_length=255, unique=True)
    cm_id = models.CharField(max_length=255)
    start = models.DateTimeField()
    due = models.DateTimeField(null=True)
    obj_type = models.CharField(max_length=100)
    course = models.CharField(max_length=500)
    title = models.CharField(max_length=100, null=True)
    state = models.CharField(max_length=10)
    video_url = models.CharField(max_length=100, null=True)
    posted = models.BooleanField()

# Create your models here.
class HealthCheck(models.Model):
    test = models.CharField(max_length=200)

class CmGradebook(models.Model):
    STATE_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    )

    course_id = models.CharField(max_length=255, null=False)
    current_page = models.IntegerField(default=0, null=True)
    count_per_gradebook = models.IntegerField(default=100)
    state = models.CharField(max_length=100, default='pending', choices=STATE_CHOICES)
    headers = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CmGradebookRecords(models.Model):
    user_email = models.EmailField()
    unit_name = models.CharField(max_length=255)
    score = models.FloatField(null=True)
    cm_gradebook = models.ForeignKey(CmGradebook)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
