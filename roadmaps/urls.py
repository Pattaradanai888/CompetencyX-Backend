from rest_framework.routers import SimpleRouter

from .views import RoleViewSet


router = SimpleRouter()
router.register('roles', RoleViewSet, basename='role')

urlpatterns = router.urls
