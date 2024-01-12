import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from opaque_keys.edx.django.models import CourseKeyField

class CreateModelIfNotExists(migrations.CreateModel):
    """
    Creates the database table if it doesn't already exist.

    This can be used to move a database model from one app to another.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # Get the name of the database table
        db_table = to_state.apps.get_model(app_label, self.name)._meta.db_table
        # If the database table for this model already exists, do nothing, otherwise
        # create the table as usual.
        if db_table in schema_editor.connection.introspection.table_names():
            print(f"{db_table} already exists. Skipping creation.")
        else:
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # Do nothing when applying this is reverse because the original creation of this
        # table was handled by edx-platform, so we don't want to delete the table on reversal.
        pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('xblock_config', '0001_initial'),
    ]

    operations = [
        CreateModelIfNotExists(
            name='CourseEditLTIFieldsEnabledFlag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('course_id', CourseKeyField(max_length=255, db_index=True)),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='Changed by')),
            ],
            options={
                'ordering': ('-change_date',),
                'abstract': False,
            },
        ),
    ]
