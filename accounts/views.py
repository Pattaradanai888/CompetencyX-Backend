from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AccountSerializer, RegistrationSerializer, SignInSerializer


def _credential_payload(user) -> dict:
    token, _created = Token.objects.get_or_create(user=user)
    return {'token': token.key, 'user': AccountSerializer(user).data}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RegistrationSerializer

    @extend_schema(
        operation_id='registerAccount',
        summary='Register an account',
        tags=['Accounts'],
        request=RegistrationSerializer,
        responses={
            201: OpenApiResponse(description='Account created; the response carries the credential to hold across requests.'),
            400: OpenApiResponse(description='Duplicate email or a password that fails validation.'),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_credential_payload(user), status=status.HTTP_201_CREATED)


class SignInView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SignInSerializer

    @extend_schema(
        operation_id='signIn',
        summary='Sign in',
        tags=['Accounts'],
        request=SignInSerializer,
        responses={
            200: OpenApiResponse(description='Credential for the signed-in respondent.'),
            400: OpenApiResponse(description='Email or password is incorrect.'),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(_credential_payload(serializer.validated_data['user']))


class SignOutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='signOut',
        summary='Sign out',
        tags=['Accounts'],
        request=None,
        responses={
            204: OpenApiResponse(description='The credential no longer authenticates.'),
            401: OpenApiResponse(description='No credential was presented.'),
        },
    )
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentAccountView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AccountSerializer

    @extend_schema(
        operation_id='getCurrentAccount',
        summary='Identify the current respondent',
        tags=['Accounts'],
        responses={
            200: OpenApiResponse(response=AccountSerializer, description='The signed-in respondent.'),
            401: OpenApiResponse(description='No credential was presented.'),
        },
    )
    def get(self, request):
        return Response(self.serializer_class(request.user).data)
