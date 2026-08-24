from django.test import TestCase

from access.models import AccessUser
from organizations.models import Company

from auditing.models import AuditEvent
from auditing.operations import record_audit_event, sanitize_audit_metadata, schedule_audit_event
from auditing.registry import AUDIT_ACTION_REGISTRY, AUDIT_CATEGORY_REGISTRY


# Define your auditing tests here.

class AuditEventTestCase(TestCase):
    """
        DOCSTRING: Audit Event Test Case

        Description:
        - Validate the core immutable auditing infrastructure.

        Notes:
        - Integration-specific audit coverage is added when each business subsystem is connected to auditing.
    """

    def setUp(self):
        self.user = AccessUser.objects.create_user(
            email="audit-admin@example.com",
            password="TestPassword123!",
        )

        self.company = Company.objects.create(
            name="Audit Company",
            code="AUDIT",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_record_audit_event(self):
        event = record_audit_event(
            category=AUDIT_CATEGORY_REGISTRY.ORGANIZATION,
            action=AUDIT_ACTION_REGISTRY.CREATE,
            description="Empresa creada.",
            actor=self.user,
            company=self.company,
            target=self.company,
            metadata={
                "company_id": self.company.id,
            },
        )

        self.assertEqual(event.company, self.company)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.category, AUDIT_CATEGORY_REGISTRY.ORGANIZATION)
        self.assertEqual(event.action, AUDIT_ACTION_REGISTRY.CREATE)
        self.assertEqual(event.target_app, "organizations")
        self.assertEqual(event.target_model, "company")
        self.assertEqual(event.target_id, str(self.company.id))

    def test_sensitive_metadata_is_redacted(self):
        metadata = sanitize_audit_metadata(
            {
                "normal": "value",
                "access_token": "secret-token",
                "nested": {
                    "password": "secret-password",
                    "safe": "visible",
                },
            }
        )

        self.assertEqual(metadata["normal"], "value")
        self.assertEqual(metadata["access_token"], "[REDACTED]")
        self.assertEqual(metadata["nested"]["password"], "[REDACTED]")
        self.assertEqual(metadata["nested"]["safe"], "visible")

    def test_audit_event_cannot_be_updated(self):
        event = record_audit_event(
            category=AUDIT_CATEGORY_REGISTRY.ORGANIZATION,
            action=AUDIT_ACTION_REGISTRY.CREATE,
            description="Empresa creada.",
            actor=self.user,
            company=self.company,
            target=self.company,
        )

        event.description = "Modified"

        with self.assertRaises(RuntimeError):
            event.save()

    def test_audit_event_cannot_be_deleted(self):
        event = record_audit_event(
            category=AUDIT_CATEGORY_REGISTRY.ORGANIZATION,
            action=AUDIT_ACTION_REGISTRY.CREATE,
            description="Empresa creada.",
            actor=self.user,
            company=self.company,
            target=self.company,
        )

        with self.assertRaises(RuntimeError):
            event.delete()

    def test_scheduled_event_is_created_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.ORGANIZATION,
                action=AUDIT_ACTION_REGISTRY.UPDATE,
                description="Empresa actualizada.",
                actor=self.user,
                company=self.company,
                target=self.company,
            )

        self.assertEqual(AuditEvent.objects.count(), 1)