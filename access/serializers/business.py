from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from ..models import AccessUser

# Define your serializers here.

class AccessUserSerializer(serializers.ModelSerializer):
    """
    DOCSTRING: User Serializer

    Description:
    - Serialize and validate the primary CentralChat user resource.
    - Validate user information used when creating application users.

    Notes:
    - The user role is controlled by the backend and cannot be assigned by the client.
    - Passwords are write-only and must never appear in API responses.
    - This serializer represents the business form of the User model.
    """

    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = AccessUser
        fields = ["id", "username", "email", "first_name", "last_name", "role", "password", "is_active"]
        read_only_fields = ["id", "role", "is_active"]

    def validate_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    """
    DOCSTRING: Login Serializer

    Description:
    - Validate credentials supplied to authenticate a CentralChat user.

    Notes:
    - Authentication uses Django's configured authentication backend.
    - Invalid credentials must return a controlled authentication error.
    """
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError({"detail": "Login rejected: invalid credentials."})
        attrs["user"] = user
        return attrs