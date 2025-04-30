from django import forms
from .models import Item, Category, StoreInventory

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

    class Meta:
        model = Item
        fields = [
            'name',
            'description',
            'category',
            'price',
            'purchase_price',
            'expiring_date',
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
        }
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Item.objects.filter(name__iexact=name).exists() and not self.instance.pk:
            raise forms.ValidationError("An item with this name already exists, Add item to existing store inventory instead.")
        return name    

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
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Select Item"
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=True,
        label="Quantity"
    )
    min_stock_level = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=True,
        label="Minimum Stock Level"
    )

    def __init__(self, *args, **kwargs):
        store = kwargs.pop('store')
        super().__init__(*args, **kwargs)
        # Only show items not already in the store's inventory
        existing_item_ids = StoreInventory.objects.filter(store=store).values_list('item_id', flat=True)
        self.fields['item'].queryset = Item.objects.exclude(id__in=existing_item_ids)