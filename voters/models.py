import os

from django.db import models


def voter_upload_path(instance, filename):
    voter_number = instance.voter.voter_number
    extension = os.path.splitext(filename)[1].lower() or ".jpg"
    folder = f"pull workers/{voter_number}"
    doc_map = {
        "national_id": "new_national_id",
        "voter_card": "new_voter_id",
    }
    base = doc_map.get(getattr(instance, "document_type", "national_id"), "document")
    return f"{folder}/{base}{extension}"


class Voter(models.Model):
    """Represents a registered voter that can access the portal."""

    voter_number = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    birth_year = models.PositiveIntegerField(blank=True, null=True)
    national_id_number = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.voter_number})"


class IDDocument(models.Model):
    """Stores identification images uploaded by voters for verification."""

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "قيد المراجعة"
        APPROVED = "approved", "مقبول"
        REJECTED = "rejected", "مرفوض"

    class DocumentType(models.TextChoices):
        NATIONAL_ID = "national_id", "الهوية الوطنية"
        VOTER_CARD = "voter_card", "بطاقة الناخب"

    voter = models.ForeignKey(
        Voter, related_name="documents", on_delete=models.CASCADE
    )
    document_type = models.CharField(
        max_length=32, choices=DocumentType.choices, default=DocumentType.NATIONAL_ID
    )
    image = models.ImageField(upload_to=voter_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    review_notes = models.TextField(blank=True)
    extracted_text = models.TextField(blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=[("passed", "تم التحقق"), ("failed", "فشل التحقق")],
        blank=True,
    )
    validation_errors = models.TextField(blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"ID for {self.voter.full_name} at {self.uploaded_at:%Y-%m-%d %H:%M}"
