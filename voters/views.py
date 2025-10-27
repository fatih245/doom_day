import os
from functools import wraps

from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import IDUploadForm, LoginForm
from .models import IDDocument, Voter
from .services.document_checks import (
    DocumentProcessingError,
    process_document_pair,
)

SESSION_KEY = "voter_id"
ADMIN_VOTER_NUMBER = os.environ.get("ADMIN_VOTER_NUMBER", "17157528")


def get_logged_in_voter(request):
    voter_id = request.session.get(SESSION_KEY)
    if not voter_id:
        return None
    try:
        return Voter.objects.get(pk=voter_id, is_active=True)
    except Voter.DoesNotExist:
        return None


def voter_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        voter = get_logged_in_voter(request)
        if not voter:
            messages.info(request, "يرجى إدخال رقم الناخب للمتابعة.")
            return redirect(f"{reverse('voters:login')}?next={request.path}")
        request.voter = voter
        return view_func(request, *args, **kwargs)

    return _wrapped


def login_view(request):
    if get_logged_in_voter(request):
        return redirect("voters:dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        voter_number = form.cleaned_data["voter_number"].strip()
        voter = Voter.objects.filter(
            voter_number__iexact=voter_number, is_active=True
        ).first()

        if voter:
            request.session[SESSION_KEY] = voter.pk
            messages.success(request, f"مرحبًا بك، {voter.full_name}!")
            next_url = request.GET.get("next")
            if not next_url:
                if voter.voter_number == ADMIN_VOTER_NUMBER:
                    next_url = reverse("voters:admin_dashboard")
                else:
                    next_url = reverse("voters:dashboard")
            return redirect(next_url)

        messages.error(
            request,
            "تعذر العثور على رقم الناخب. يرجى التحقق والمحاولة مرة أخرى.",
        )

    return render(request, "voters/login.html", {"form": form})


@voter_login_required
def dashboard(request):
    voter = request.voter
    if voter.voter_number == ADMIN_VOTER_NUMBER:
        return redirect("voters:admin_dashboard")
    documents = voter.documents.all()

    if request.method == "POST":
        form = IDUploadForm(request.POST, request.FILES)
        if form.is_valid():
            national_image = form.cleaned_data["national_id_image"]
            voter_card_image = form.cleaned_data["voter_card_image"]

            def _prepare_document(uploaded_file, doc_type):
                uploaded_file.seek(0)
                data = uploaded_file.read()
                uploaded_file.seek(0)

                if not data:
                    raise DocumentProcessingError("الملف المرفوع فارغ.")

                ext = os.path.splitext(uploaded_file.name or "")[1].lower() or ".jpg"
                folder = f"pull workers/{voter.voter_number}"
                base_name = (
                    "national_id"
                    if doc_type == IDDocument.DocumentType.NATIONAL_ID
                    else "voter_id"
                )

                original_rel = f"{folder}/original_{base_name}{ext}"
                processed_rel = f"{folder}/new_{base_name}{ext}"

                for rel_path in (original_rel, processed_rel):
                    if default_storage.exists(rel_path):
                        default_storage.delete(rel_path)

                default_storage.save(original_rel, ContentFile(data))

                processed_content = ContentFile(data)
                processed_content.name = f"new_{base_name}{ext}"

                document = IDDocument.objects.create(
                    voter=voter,
                    document_type=doc_type,
                    image=processed_content,
                )

                return document

            try:
                with transaction.atomic():
                    national_doc = _prepare_document(
                        national_image, IDDocument.DocumentType.NATIONAL_ID
                    )
                    voter_doc = _prepare_document(
                        voter_card_image, IDDocument.DocumentType.VOTER_CARD
                    )
                    process_document_pair(national_doc, voter_doc)
            except DocumentProcessingError as exc:
                messages.error(request, f"حدث خطأ أثناء تحليل الصور: {exc}")
                return redirect("voters:dashboard")
            except Exception as exc:  # pragma: no cover - defensive
                messages.error(
                    request, f"حدث خطأ غير متوقع أثناء رفع الصور: {exc}"
                )
                return redirect("voters:dashboard")

            failed_docs = [
                doc
                for doc in (national_doc, voter_doc)
                if doc.validation_status == "failed"
            ]
            if failed_docs:
                error_messages = " ".join(
                    f"{doc.get_document_type_display()}: {doc.validation_errors}"
                    for doc in failed_docs
                    if doc.validation_errors
                )
                messages.error(
                    request,
                    error_messages
                    or "فشلت عملية التحقق. يرجى التأكد من وضوح الصور والمحاولة مرة أخرى.",
                )
            else:
                messages.success(
                    request,
                    "تم رفع الصورتين بنجاح والتحقق من البيانات آليًا.",
                )
            return redirect("voters:dashboard")
        messages.error(request, "يرجى تصحيح الأخطاء ثم المحاولة مرة أخرى.")
    else:
        form = IDUploadForm()

    national_docs = documents.filter(
        document_type=IDDocument.DocumentType.NATIONAL_ID
    )
    voter_card_docs = documents.filter(
        document_type=IDDocument.DocumentType.VOTER_CARD
    )

    context = {
        "form": form,
        "voter": voter,
        "national_docs": national_docs,
        "voter_card_docs": voter_card_docs,
        "is_admin": voter.voter_number == ADMIN_VOTER_NUMBER,
    }
    return render(request, "voters/dashboard.html", context)


def logout_view(request):
    request.session.pop(SESSION_KEY, None)
    messages.info(request, "تم تسجيل الخروج بنجاح.")
    return redirect("voters:login")


@voter_login_required
def admin_dashboard(request):
    voter = request.voter
    if voter.voter_number != ADMIN_VOTER_NUMBER:
        messages.error(request, "لا تملك صلاحية الوصول إلى لوحة الإدارة.")
        return redirect("voters:dashboard")

    voters_qs = (
        Voter.objects.prefetch_related("documents")
        .annotate(total_uploads=Count("documents"))
        .order_by("full_name")
    )

    rows = []
    summary = {
        "total": voters_qs.count(),
        "with_uploads": 0,
        "completed": 0,
        "pending": 0,
        "failed": 0,
    }

    for person in voters_qs:
        docs = list(person.documents.all())
        national_docs = [doc for doc in docs if doc.document_type == IDDocument.DocumentType.NATIONAL_ID]
        voter_docs = [doc for doc in docs if doc.document_type == IDDocument.DocumentType.VOTER_CARD]

        latest_upload = max((doc.uploaded_at for doc in docs if doc.uploaded_at), default=None)
        total_uploads = len(docs)
        has_both = bool(national_docs) and bool(voter_docs)
        passed_all = (
            has_both
            and all(doc.validation_status == "passed" for doc in national_docs + voter_docs if doc.validation_status)
        )
        any_failed = any(doc.validation_status == "failed" for doc in docs)

        if total_uploads == 0:
            status_key = "missing"
            status_label = "لم يتم الرفع"
        elif passed_all:
            status_key = "verified"
            status_label = "مكتمل"
        elif any_failed:
            status_key = "failed"
            status_label = "فشل التحقق"
        else:
            status_key = "pending"
            status_label = "قيد المراجعة"

        summary["with_uploads"] += int(total_uploads > 0)
        if status_key == "verified":
            summary["completed"] += 1
        elif status_key == "failed":
            summary["failed"] += 1
        elif status_key in {"pending"}:
            summary["pending"] += 1

        rows.append(
            {
                "person": person,
                "total_uploads": total_uploads,
                "has_national": bool(national_docs),
                "has_voter_card": bool(voter_docs),
                "latest_upload": latest_upload,
                "status_key": status_key,
                "status_label": status_label,
                "national_status": national_docs[0].validation_status if national_docs else "",
                "voter_status": voter_docs[0].validation_status if voter_docs else "",
            }
        )

    context = {
        "summary": summary,
        "rows": rows,
        "admin_voter": voter,
    }

    return render(request, "voters/admin_dashboard.html", context)
