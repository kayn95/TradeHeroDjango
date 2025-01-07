# trades/admin.py

from django.contrib import admin
from .models import Trade, Strategy
from .models import Profile, CoachRequest

admin.site.register(Trade)
admin.site.register(Strategy)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_coach', 'coach')
    list_filter = ('is_coach',)

@admin.register(CoachRequest)
class CoachRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'coach', 'accepted', 'created_at')
    list_filter = ('accepted',)
