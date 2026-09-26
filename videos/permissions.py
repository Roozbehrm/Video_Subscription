from rest_framework.permissions import BasePermission

from subscriptions.services import user_can_access


class HasVideoAccess(BasePermission):

    def has_object_permission(self, request, view, obj):
        return user_can_access(request.user, obj)
