from django import forms
from properties.models import Property, PropertyImage


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        default_attrs = {"multiple": True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            single_clean = super().clean
            return [single_clean(d, initial) for d in data]
        return super().clean(data, initial)


class PropertyForm(forms.ModelForm):
    custom_features = forms.CharField(
        required=False,
        label="Additional features",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "e.g. Parking space, Spa, Fitness center, Underfloor heating, Smart home"
            }
        )
    )

    images = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            "class": "form-control",
            "id": "id_images",
            "accept": "image/*"
        })
    )

    delete_images = forms.ModelMultipleChoiceField(
        queryset=PropertyImage.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    ai_prompt = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "id": "id_ai_prompt",
            "rows": 2,
            "placeholder": "Optional: guide the AI (e.g. make it luxurious, mention pets allowed, highlight family-friendly features)"
        })
    )

    class Meta:
        model = Property
        exclude = ["owner", "status"]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter property name"}),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "id": "description-field",
                "rows": 5,
                "placeholder": "Write a description or generate one with AI..."
            }),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Price in €"}),
            "area": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Area in m²"}),
            "rooms": forms.NumberInput(
                attrs={"class": "form-control", "required": False, "placeholder": "Number of rooms"}),
            "bedrooms": forms.NumberInput(
                attrs={"class": "form-control", "required": False, "placeholder": "Number of bedrooms"}),
            "bathrooms": forms.NumberInput(
                attrs={"class": "form-control", "required": False, "placeholder": "Number of bathrooms"}),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter city"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Street, neighborhood, etc."}),
            "property_type": forms.Select(attrs={"class": "form-select"}),
            "features": forms.SelectMultiple(
                attrs={"class": "form-select", "id": "features-select"}
            ),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        if instance:
            self.fields['delete_images'].queryset = instance.images.all()
