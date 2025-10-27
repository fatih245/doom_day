from django.contrib import admin

from .models import IDDocument, Voter


class IDDocumentInline(admin.TabularInline):
    model = IDDocument
    extra = 0
    readonly_fields = (
        "uploaded_at",
        "review_status",
        "validation_status",
        "validation_errors",
        "extracted_text",
    )
    fields = (
        "document_type",
        "image",
        "uploaded_at",
        "review_status",
        "validation_status",
        "validation_errors",
        "extracted_text",
    )


@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "voter_number",
        "national_id_number",
        "birth_year",
        "email",
        "is_active",
    )
    search_fields = ("full_name", "voter_number", "national_id_number", "email")
    list_filter = ("is_active",)
    inlines = [IDDocumentInline]


@admin.register(IDDocument)
class IDDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "voter",
        "document_type",
        "review_status",
        "validation_status",
        "uploaded_at",
    )
    list_filter = ("document_type", "review_status", "validation_status", "uploaded_at")
    search_fields = ("voter__full_name", "voter__voter_number")
