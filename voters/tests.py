import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import IDDocument, Voter


class VoterPortalViewTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media)
        self.override.enable()

        self.voter = Voter.objects.create(
            voter_number="16737639",
            full_name="دنيا عباس فاضل",
            email="ada@example.com",
            national_id_number="200661668131",
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def _sample_image(self, color=(255, 0, 0)):
        buffer = BytesIO()
        image = Image.new("RGB", (50, 50), color=color)
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(
            "sample.png",
            buffer.getvalue(),
            content_type="image/png",
        )

    def test_valid_voter_login(self):
        response = self.client.post(
            reverse("voters:login"), {"voter_number": "16737639"}, follow=True
        )
        self.assertRedirects(response, reverse("voters:dashboard"))
        self.assertContains(response, self.voter.full_name)

    def test_invalid_voter_number_rejected(self):
        response = self.client.post(
            reverse("voters:login"), {"voter_number": "INVALID"}, follow=True
        )
        self.assertContains(response, "تعذر العثور على رقم الناخب")
        self.assertTemplateUsed(response, "voters/login.html")

    @patch("voters.views.process_document_pair")
    def test_upload_id_document_flow(self, mock_process_pair):
        # Mock OCR outcome to mark documents as passed
        def _fake_process(national_doc, voter_doc):
            national_doc.validation_status = "passed"
            national_doc.validation_errors = ""
            national_doc.extracted_text = "200661668131"
            national_doc.save(
                update_fields=["validation_status", "validation_errors"]
            )
            voter_doc.validation_status = "passed"
            voter_doc.validation_errors = ""
            voter_doc.extracted_text = "16750006"
            voter_doc.save(update_fields=["validation_status", "validation_errors"])

        mock_process_pair.side_effect = _fake_process

        # Authenticate voter
        self.client.post(reverse("voters:login"), {"voter_number": "16737639"})

        response = self.client.post(
            reverse("voters:dashboard"),
            {
                "national_id_image": self._sample_image(),
                "voter_card_image": self._sample_image(color=(0, 255, 0)),
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("voters:dashboard"))
        self.assertEqual(
            IDDocument.objects.filter(
                voter=self.voter,
                document_type=IDDocument.DocumentType.NATIONAL_ID,
            ).count(),
            1,
        )
        self.assertEqual(
            IDDocument.objects.filter(
                voter=self.voter,
                document_type=IDDocument.DocumentType.VOTER_CARD,
            ).count(),
            1,
        )
        self.assertContains(response, "تم رفع الصورتين بنجاح")

        target_dir = Path(settings.MEDIA_ROOT) / "pull workers" / self.voter.voter_number
        self.assertTrue((target_dir / "original_national_id.png").exists())
        self.assertTrue((target_dir / "original_voter_id.png").exists())
        self.assertTrue((target_dir / "new_national_id.png").exists())
        self.assertTrue((target_dir / "new_voter_id.png").exists())


class DocumentCheckTests(TestCase):
    def test_validate_national_id_sets_birth_year_and_number(self):
        voter = Voter.objects.create(
            voter_number="999",
            full_name="اختبار",
        )
        from voters.services.document_checks import _validate_national_id

        errors = _validate_national_id(voter, "الرقم الوطني 200661668131")
        self.assertEqual(errors, [])
        self.assertEqual(voter.birth_year, 2006)
        self.assertEqual(voter.national_id_number, "200661668131")
