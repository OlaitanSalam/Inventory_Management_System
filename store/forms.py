from django import forms
from .models import Item, Category, StoreInventory, Variety

class ItemForm(forms.ModelForm):
    """
    A form for creating or updating an Item in the inventory.
    """
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False
    )
    min_stock_level = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False
    )
    store_price = forms.FloatField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Store-Specific Price (overrides base price if set)"
    )

    class Meta:
        model = Item
        fields = [
            'name',
            'description',
            'category',
            'price',
            'purchase_price',
            'expiring_date',
            'has_varieties',
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 2
                }
            ),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'step': '0.01'
                }
            ),
            'purchase_price': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'step': '0.01'}
            ),
            'expiring_date': forms.DateTimeInput(
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local'
                }
            ),
            'has_varieties': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Item.objects.filter(name__iexact=name).exists() and not self.instance.pk:
            raise forms.ValidationError("An item with this name already exists, Add item to existing store inventory instead.")
        return name 
    def clean(self):
        cleaned_data = super().clean()
        has_varieties = cleaned_data.get('has_varieties')
        price = cleaned_data.get('price')
        if has_varieties and price is not None and price > 0:
            raise forms.ValidationError("Items with varieties should not have a price.")
        return cleaned_data

class VarietyForm(forms.ModelForm):
    class Meta:
        model = Variety
        fields = ['name', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }   

class CategoryForm(forms.ModelForm):
    """
    A form for creating or updating category.
    """
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name',
                'aria-label': 'Category Name'
            }),
        }
        labels = {
            'name': 'Category Name',
        }

class AddExistingItemForm(forms.Form):
    """
    A form for adding an existing item to a store's inventory.
    """
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),  # Queryset will be set dynamically
        widget=forms.Select(attrs={'class': 'form-control select2-item'}),
        label="Select Item",
        required=False  # Make optional to allow empty rows
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False,  # Make optional to allow empty rows
        label="Quantity",
        initial=0
    )
    min_stock_level = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False,  # Make optional to allow empty rows
        label="Minimum Stock Level",
        initial=0
    )

    def __init__(self, *args, **kwargs):
        store = kwargs.pop('store')
        super().__init__(*args, **kwargs)
        # Only show items not already in the store's inventory
        existing_item_ids = StoreInventory.objects.filter(store=store).values_list('item_id', flat=True)
        self.fields['item'].queryset = Item.objects.exclude(id__in=existing_item_ids)
        
    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        quantity = cleaned_data.get('quantity')
        min_stock_level = cleaned_data.get('min_stock_level')
        
        # If any field is filled, require all fields
        if any([item, quantity is not None, min_stock_level is not None]):
            if not item:
                self.add_error('item', 'Item is required when other fields are filled')
            if quantity is None:
                self.add_error('quantity', 'Quantity is required when other fields are filled')
            if min_stock_level is None:
                self.add_error('min_stock_level', 'Minimum stock level is required when other fields are filled')
        
        return cleaned_data