"""Audit service (shared across apps).

Centralizes the creation of append-only audit events so consuming apps never
couple to the views module. The AuditEvent model remains in organizations
(models.py) and is not moved between applications; migrations, tables and
relations are untouched.

The helper is imported by apps.organizations.views and apps.accounts.views.
Every call must stay inside the same transaction.atomic() block as the change
it records: a failure propagates and rolls the change back, so a mutation is
never reported successful unless its audit record persisted.
"""

from .models import AuditEvent


def _audit(actor, organization, action, target_type, target_id, metadata=None):
    """Create one audit event.

    Any failure propagates so the caller's atomic block rolls back the
    accompanying change: a change is never reported successful unless its
    audit record persisted (Slice 2 spec S6).
    """
    return AuditEvent.objects.create(
        actor=actor,
        organization=organization,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
    )