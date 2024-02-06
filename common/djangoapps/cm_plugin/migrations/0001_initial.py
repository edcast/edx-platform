# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [

    ]
    operations = [
        migrations.CreateModel(
            name='XModule_Metadata_Cache',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('url', models.CharField(unique=True, max_length=255)),
                ('cm_id', models.CharField(max_length=255)),
                ('start', models.DateTimeField()),
                ('due', models.DateTimeField(null=True)),
                ('obj_type', models.CharField(max_length=100)),
                ('course', models.CharField(max_length=500)),
                ('title', models.CharField(max_length=100, null=True)),
                ('state', models.CharField(max_length=10)),
                ('video_url', models.CharField(max_length=100, null=True)),
                ('posted', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='HealthCheck',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('test', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='CmGradebook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', models.CharField(max_length=255)),
                ('current_page', models.IntegerField(default=0, null=True)),
                ('count_per_gradebook', models.IntegerField(default=100)),
                ('state', models.CharField(default='pending', max_length=100)),
                ('headers', models.TextField(null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='CmGradebookRecords',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_email', models.EmailField(default=None, max_length=75)),
                ('unit_name', models.CharField(max_length=255)),
                ('score', models.FloatField(null=True)),
                ('cm_gradebook', models.ForeignKey(to='cm_plugin.CmGradebook', on_delete=models.CASCADE)),
                ('created_at', models.DateTimeField(auto_now_add=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True, blank=True)),
            ],

        ),
        migrations.AlterUniqueTogether(
            name='cmgradebookrecords',
            unique_together=set([('user_email', 'unit_name', 'cm_gradebook_id')]),
        ),
    ]