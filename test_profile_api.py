import os
import sys
import django
from io import BytesIO
from PIL import Image

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreAPI.settings')
django.setup()

from rest_framework.test import APIClient
from accounts.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

def run_tests():
    user, created = User.objects.get_or_create(username="testuser", defaults={"email": "testuser@example.com"})
    user.set_password("Password123!")
    user.save()

    client = APIClient()
    client.force_authenticate(user=user)

    print("--- GET Profile ---")
    res = client.get('/api/users/me/')
    if res.status_code != 200:
        res = client.get('/api/auth/profile/') # test endpoints
    print("GET status:", res.status_code, res.data)

    # Create dummy image
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    img.save(img_io, format='JPEG')
    img_io.seek(0)
    uploaded_file = SimpleUploadedFile("avatar.jpg", img_io.read(), content_type="image/jpeg")

    print("\n--- PATCH Profile with avatar file ---")
    res_patch = client.patch('/api/users/me/', {'avatar': uploaded_file}, format='multipart')
    print("PATCH status:", res_patch.status_code)
    print("PATCH response:", res_patch.data)

    # Reset uploaded_file
    img_io.seek(0)
    uploaded_file = SimpleUploadedFile("avatar2.jpg", img_io.read(), content_type="image/jpeg")

    print("\n--- PUT Profile with avatar file ---")
    res_put = client.put('/api/users/me/', {'username': 'testuser', 'first_name': 'Test', 'last_name': 'User', 'avatar': uploaded_file}, format='multipart')
    print("PUT status:", res_put.status_code)
    print("PUT response:", res_put.data)

if __name__ == "__main__":
    run_tests()
