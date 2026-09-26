from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, VideoViewSet

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("videos", VideoViewSet, basename="video")

urlpatterns = router.urls
