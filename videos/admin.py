from django.contrib import admin

from .models import Category, Comment, Rating, Video

admin.site.register(Category)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "min_tier", "is_published", "views_count", "avg_rating")
    list_filter = ("min_tier", "is_published", "category")
    search_fields = ("title",)


admin.site.register(Rating)
admin.site.register(Comment)
