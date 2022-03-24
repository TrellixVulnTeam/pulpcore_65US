# Generated by Django 2.2.15 on 2020-09-02 04:27

import uuid

from django.db import migrations, models


def fill_in_resource_id(apps, schema_editor):
    # Fills in _resource_job_id with a random UUID, it won't matter because
    # it's only used for new ones.
    Task = apps.get_model('core', 'Task')
    for task in Task.objects.all():
        task._resource_job_id = uuid.uuid4()
        task.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_accesspolicy_permissions_allow_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='_resource_job_id',
            field=models.UUIDField(null=True),
        ),
        migrations.RunPython(fill_in_resource_id, reverse_code=migrations.RunPython.noop, elidable=True),
        migrations.AlterField(
            model_name='task',
            name='_resource_job_id',
            field=models.UUIDField()
        )
    ]
