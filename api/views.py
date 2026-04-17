from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(
    operation_id='healthCheck',
    summary='Health check',
    tags=['Health'],
    responses={
        200: OpenApiResponse(
            response=None,
            description='API health status.',
            examples=[
                OpenApiExample(
                    'Healthy response',
                    value={'status': 'ok'},
                    response_only=True,
                ),
            ],
        ),
    },
)
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok'})
