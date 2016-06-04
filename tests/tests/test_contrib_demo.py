import datetime

from django.test import TestCase, override_settings

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import migrations, models, connection
from django.db.migrations.state import ProjectState
from django.utils import timezone, six

from .utils import get_table_list

from boardinghouse.contrib.demo import apps
from boardinghouse.contrib.demo.models import DemoSchema, DemoSchemaExpired

CREDENTIALS = {
    'username': 'username',
    'password': 'password'
}


class TestContribDemo(TestCase):
    def test_demo_schema_name(self):
        user = User.objects.create_user(**CREDENTIALS)
        schema = DemoSchema.objects.create(user=user)
        self.assertEqual('Demo schema', six.text_type(schema.name))

    def test_demo_schema_str(self):
        demo = DemoSchema(user=User(username='user'), expires_at=datetime.datetime.now() + datetime.timedelta(1))
        self.assertTrue(six.text_type(demo).startswith('Demo for user: expires at'))
        demo.expires_at = datetime.datetime(1970, 1, 1)
        self.assertTrue(six.text_type(demo).startswith('Expired demo for user (expired'))

    def test_demo_can_be_created_and_activated(self):
        user = User.objects.create_user(**CREDENTIALS)
        schema = DemoSchema.objects.create(user=user)
        schema.activate()
        schema.deactivate()

    def test_demo_can_only_be_activated_by_user(self):
        User.objects.create_user(**CREDENTIALS)
        other = User.objects.create_user(username='other', password='password')
        DemoSchema.objects.create(user=other)

        self.client.login(**CREDENTIALS)
        response = self.client.get('/aware/?__schema=__demo_{}'.format(other.pk))
        self.assertEqual(403, response.status_code)

    def test_demo_can_be_activated_by_user(self):
        user = User.objects.create_user(**CREDENTIALS)
        DemoSchema.objects.create(user=user)
        self.client.login(**CREDENTIALS)
        response = self.client.get('/__change_schema__/__demo_{}/'.format(user.pk))
        self.assertEqual(200, response.status_code)

    def test_activation_of_expired_demo_raises(self):
        user = User.objects.create_user(**CREDENTIALS)
        schema = DemoSchema.objects.create(user=user, expires_at=timezone.now())
        with self.assertRaises(DemoSchemaExpired):
            schema.activate()

    def test_cleanup_expired_removes_expired(self):
        user = User.objects.create_user(**CREDENTIALS)
        DemoSchema.objects.create(user=user, expires_at='1970-01-01')

        call_command('cleanup_expired_demos')

        self.assertEqual(0, DemoSchema.objects.count())

    def test_demo_admin(self):
        User.objects.create_superuser(email='email@example.com', **CREDENTIALS)
        DemoSchema.objects.create(user=User.objects.create_user(username='a', password='a'),
                                  expires_at='1970-01-01')
        DemoSchema.objects.create(user=User.objects.create_user(username='b', password='b'),
                                  expires_at='9999-01-01')

        self.client.login(**CREDENTIALS)

        response = self.client.get('/admin/demo/demoschema/')
        self.assertContains(response, '/static/admin/img/icon-no', count=1, status_code=200)
        self.assertContains(response, '/static/admin/img/icon-yes', count=1, status_code=200)

    def test_demo_schemata_get_migrated(self):
        user = User.objects.create_user(**CREDENTIALS)
        schema = DemoSchema.objects.create(user=user)

        operation = migrations.CreateModel("Pony", [
            ('pony_id', models.AutoField(primary_key=True)),
            ('pink', models.IntegerField(default=1)),
        ])
        project_state = ProjectState()
        new_state = project_state.clone()
        operation.state_forwards('tests', new_state)

        schema.activate()
        self.assertFalse('tests_pony' in get_table_list())

        with connection.schema_editor() as editor:
            operation.database_forwards('tests', editor, project_state, new_state)
        schema.activate()
        self.assertTrue('tests_pony' in get_table_list())

        with connection.schema_editor() as editor:
            operation.database_backwards('tests', editor, new_state, project_state)
        schema.activate()
        self.assertFalse('tests_pony' in get_table_list())

    @override_settings(BOARDINGHOUSE_DEMO_PERIOD=datetime.timedelta(7))
    def test_default_expiry_period_from_settings(self):
        user = User.objects.create_user(**CREDENTIALS)
        schema = DemoSchema.objects.create(user=user)

        self.assertEqual(datetime.datetime.utcnow().date() + datetime.timedelta(7), schema.expires_at.date())

    @override_settings(BOARDINGHOUSE_DEMO_PERIOD='not-a-valid-timedelta')
    def test_invalid_expiry(self):
        errors = apps.check_demo_expiry_is_timedelta()
        self.assertEqual(1, len(errors))
        self.assertEqual('boardinghouse.contrib.demo.E002', errors[0].id)

    @override_settings(BOARDINGHOUSE_DEMO_PREFIX='demo_')
    def test_invalid_prefix(self):
        errors = apps.check_demo_prefix_stats_with_underscore()
        self.assertEqual(1, len(errors))
        self.assertEqual('boardinghouse.contrib.demo.E001', errors[0].id)
