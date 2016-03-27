from copy import deepcopy

from django.conf import settings
from django.test import TestCase, modify_settings
from django.core import checks

from boardinghouse import apps


class TestSettings(TestCase):
    def test_all_settings(self):
        self.assertEqual([], apps.check_db_backend())
        self.assertEqual([], apps.check_middleware_installed())
        self.assertEqual([], apps.check_session_middleware_installed())
        self.assertEqual([], apps.check_installed_before_admin())
        self.assertEqual([], apps.check_context_processor_installed())

    @modify_settings()
    def test_database_engine_not_valid(self):
        original = settings.DATABASES['default']['ENGINE']
        settings.DATABASES['default']['ENGINE'] = 'foo.bar.baz'
        # Django 1.7 testing on codeship breaks without this?
        try:
            errors = apps.check_db_backend()
            self.assertEqual(1, len(errors))
            self.assertTrue(isinstance(errors[0], checks.Error))
            self.assertEqual('boardinghouse.E001', errors[0].id)
        finally:
            settings.DATABASES['default']['ENGINE'] = original

    @modify_settings(MIDDLEWARE_CLASSES={'remove': [apps.MIDDLEWARE]})
    def test_middleware_missing(self):
        errors = apps.check_middleware_installed()
        self.assertEqual(1, len(errors))
        self.assertTrue(isinstance(errors[0], checks.Error))
        self.assertEqual('boardinghouse.E003', errors[0].id)

    @modify_settings(MIDDLEWARE_CLASSES={'remove': [
        'django.contrib.sessions.middleware.SessionMiddleware']})
    def test_session_middleware_missing(self):
        errors = apps.check_session_middleware_installed()
        self.assertEqual(1, len(errors))
        self.assertTrue(isinstance(errors[0], checks.Error))
        self.assertEqual('boardinghouse.E002', errors[0].id)

    @modify_settings()
    def test_installed_before_admin(self):
        settings.INSTALLED_APPS.remove('boardinghouse')
        settings.INSTALLED_APPS.append('boardinghouse')
        errors = apps.check_installed_before_admin()
        self.assertEqual(1, len(errors))
        self.assertTrue(isinstance(errors[0], checks.Error))
        self.assertEqual('boardinghouse.E004', errors[0].id)

    @modify_settings(INSTALLED_APPS={
        'remove': ['django.contrib.admin'],
    })
    def test_admin_not_installed(self):
        errors = apps.check_installed_before_admin()
        self.assertEqual(0, len(errors))

    @modify_settings()
    def test_context_processor_not_installed_in_TEMPLATES(self):
        templates = deepcopy(settings.TEMPLATES)
        templates[0]['OPTIONS']['context_processors'].remove(apps.CONTEXT)
        with self.settings(TEMPLATES=templates):
            errors = apps.check_context_processor_installed()
            self.assertEqual(1, len(errors))
            self.assertTrue(isinstance(errors[0], checks.Warning))
            self.assertEqual('boardinghouse.W001', errors[0].id)

    @modify_settings(TEMPLATE_CONTEXT_PROCESSORS={'remove': apps.CONTEXT})
    def test_context_processor_not_installed_in_TEMPLATE_CONTEXT_PROCESSORS(self):
        del settings.TEMPLATES
        errors = apps.check_context_processor_installed()
        self.assertEqual(1, len(errors))
        self.assertTrue(isinstance(errors[0], checks.Warning))
        self.assertEqual('boardinghouse.W001', errors[0].id)

    @modify_settings()
    def test_no_context_processors_found(self):
        del settings.TEMPLATES
        del settings.TEMPLATE_CONTEXT_PROCESSORS
        errors = apps.check_context_processor_installed()
        self.assertEqual(1, len(errors))
        self.assertTrue(isinstance(errors[0], checks.Warning))
        self.assertEqual('boardinghouse.W001', errors[0].id)

    @modify_settings()
    def test_context_processor_installed_in_TEMPLATE_CONTEXT_PROCESSORS(self):
        del settings.TEMPLATES
        self.assertEqual([], apps.check_context_processor_installed())
