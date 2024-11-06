import django
from django.contrib.auth.models import User

username='admin'
email='admin@example.com'
password='Wkdwogur1@'
User.objects.create_superuser(username=username, email=email, password=password)