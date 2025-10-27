from django import forms


class LoginForm(forms.Form):
    voter_number = forms.CharField(
        label="رقم الناخب",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "placeholder": "أدخل رقم الناخب الخاص بك",
                "class": "form-input",
                "autofocus": True,
                "dir": "ltr",
            }
        ),
    )


class IDUploadForm(forms.Form):
    national_id_image = forms.ImageField(
        label="صورة الهوية الوطنية (الوجه الأمامي)",
        widget=forms.FileInput(
            attrs={
                "accept": "image/*",
                "class": "form-input",
            }
        ),
    )
    voter_card_image = forms.ImageField(
        label="صورة بطاقة الناخب (الوجه الأمامي)",
        widget=forms.FileInput(
            attrs={
                "accept": "image/*",
                "class": "form-input",
            }
        ),
    )

    def _validate_size(self, image):
        max_mb = 10
        if image.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"حجم الصورة أكبر من {max_mb} ميغابايت.")
        return image

    def clean_national_id_image(self):
        image = self.cleaned_data["national_id_image"]
        return self._validate_size(image)

    def clean_voter_card_image(self):
        image = self.cleaned_data["voter_card_image"]
        return self._validate_size(image)
