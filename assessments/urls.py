from rest_framework.routers import SimpleRouter

from .views import AssessmentSessionViewSet


router = SimpleRouter()
router.register('', AssessmentSessionViewSet, basename='assessment-session')

urlpatterns = router.urls
