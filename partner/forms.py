from django import forms
from .models import BadmintonCenter, Amenity,Court

class BadmintonCenterForm(forms.ModelForm):
    
    open_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}), label="Giờ mở cửa")
    close_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}), label="Giờ đóng cửa")
    
    
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = BadmintonCenter
        fields = [
            'name', 'address', 'latitude', 'longitude', 'description', 'image', 
            'open_time', 'close_time', 'amenities', 'is_active'
        ]
        
        widgets = {
            # 1. Các trường nhập liệu cơ bản
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ví dụ: Sân Cầu Lông Cầu Giấy Arena'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Số 123, Đường ABC...'
            }),
            
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Mô tả ngắn về sân bãi, chỗ gửi xe...'
            }),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            
            
            'open_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'close_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            
            
            'amenities': forms.CheckboxSelectMultiple(),

            
            'latitude': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'id_latitude'}),
            'longitude': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'id_longitude'}),
            
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_active'}),
        }


class CourtForm(forms.ModelForm):
    class Meta:
        model = Court
        fields = [
           'name', 'type_court', 'base_price_per_hour','golden_price_per_hour','golden_start_time','golden_end_time', 'is_active'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ví dụ: Sân Cầu Lông Cầu Giấy Arena'
            }),
            'type_court': forms.Select(attrs={'class': 'form-select'}),
            'base_price_per_hour': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': 10000,
                'min' : 0,
                'placeholder': 'giá tiền mỗi giờ'
            }),
            'golden_price_per_hour': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': 10000,
                'min' : 0,
                'placeholder': 'giá tiền mỗi giờ'
            }),
            'golden_start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'golden_end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'courtActive'}),
        }