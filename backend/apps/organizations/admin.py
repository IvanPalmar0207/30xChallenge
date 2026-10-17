from django.contrib import admin

from .models import AuditEvent, Organization, OrganizationMembership, Vendor


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active")
    list_filter = ("role", "is_active", "organization")
    search_fields = ("user__username", "organization__name")


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    """Read-only vendor surface.

    Vendors are managed exclusively through the audited API endpoints; the
    admin is registered read-only so no alternate, un-audited mutation path
    exists (Slice 3 spec S6).
    """

    list_display = ("legal_name", "organization", "tax_id", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("legal_name", "tax_id", "organization__name")
    ordering = ("-created_at",)
    readonly_fields = [
        "id",
        "organization",
        "legal_name",
        "tax_id",
        "status",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only view of the append-only audit trail (superuser surface).

    Regular API users have no audit endpoints at all; the Django admin is the
    only authorized read path in this slice.
    """

    list_display = (
        "created_at",
        "actor",
        "organization",
        "action",
        "target_type",
        "target_id",
    )
    list_filter = ("action", "organization")
    search_fields = ("actor__username", "target_type", "target_id")
    ordering = ("-created_at",)
    readonly_fields = [
        "id",
        "actor",
        "organization",
        "action",
        "target_type",
        "target_id",
        "metadata",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
