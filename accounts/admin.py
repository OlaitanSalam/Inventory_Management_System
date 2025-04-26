from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Profile, Vendor
from .forms import CreateUserForm, UserUpdateForm

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    """Admin interface for the Vendor model."""
    fields = ('name', 'phone_number', 'address')
    list_display = ('name',  'address')
    search_fields = ('name', 'phone_number', 'address')
    list_per_page = 15
    


@admin.register(Profile)
class CustomProfileAdmin(UserAdmin):
    # Use your custom forms for creating and updating profiles.
    add_form = CreateUserForm
    form = UserUpdateForm
    model = Profile

    list_display = ('email', 'first_name', 'last_name', 'store', 'role', 'is_staff')
    list_filter = ('role', 'status', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    list_per_page = 15

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'telephone', 'profile_picture')}),
        (_('Work info'), {'fields': ('store', 'role', 'status')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2',
                'first_name', 'last_name', 'store', 'role', 'status', 'telephone', 'profile_picture',
            ),
        }),
    )
