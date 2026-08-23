from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


User = get_user_model()

INVALID_CREDENTIALS_MESSAGE = 'Email or password is incorrect.'

# The email doubles as Django's username, so it cannot outgrow that column.
EMAIL_MAX_LENGTH = User._meta.get_field('username').max_length


def normalize_email(value: str) -> str:
    """The stored form of an email: one account per address regardless of how it was typed."""
    return User.objects.normalize_email(value).lower()


class AccountSerializer(serializers.ModelSerializer):
    """The identity a signed-in respondent gets back when they ask who they are."""

    class Meta:
        model = User
        fields = ('id', 'email')
        read_only_fields = fields


class CredentialSerializer(serializers.Serializer):
    """The email and password pair a respondent presents to register or to sign in."""

    email = serializers.EmailField(max_length=EMAIL_MAX_LENGTH)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class RegistrationSerializer(CredentialSerializer):
    def validate_email(self, value):
        email = normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            msg = 'An account with this email already exists.'
            raise serializers.ValidationError(msg)
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        # The email is the identifier a respondent signs in with; Django's default
        # user model still requires a username, so it carries the same value.
        return User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
        )


class SignInSerializer(CredentialSerializer):
    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            username=normalize_email(attrs['email']),
            password=attrs['password'],
        )
        # An unknown email and a wrong password are refused identically, so the
        # response does not disclose which accounts exist.
        if user is None:
            raise serializers.ValidationError({'detail': INVALID_CREDENTIALS_MESSAGE})
        attrs['user'] = user
        return attrs
