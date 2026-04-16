from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(
    responses={200: OpenApiResponse(description='API health status.')},
)
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok'})
