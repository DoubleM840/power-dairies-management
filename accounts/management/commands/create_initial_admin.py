from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Creates the initial admin superuser if it does not exist'

    def handle(self, *args, **kwargs):
        # Default admin credentials
        admin_username = 'admin'
        admin_email = 'admin@powerdairies.com'
        admin_password = 'admin123'  # Change this in production!

        # Check if admin already exists
        if User.objects.filter(username=admin_username).exists():
            self.stdout.write(self.style.WARNING(f'Admin user "{admin_username}" already exists.'))
            return

        # Create superuser
        admin_user = User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            first_name='System',
            last_name='Administrator'
        )

        # Update profile
        profile = admin_user.profile
        profile.role = 'admin'
        profile.is_active_account = True
        profile.save()

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created admin superuser:\n'
            f'  Username: {admin_username}\n'
            f'  Password: {admin_password}\n'
            f'  Email: {admin_email}\n'
            f'  URL: http://127.0.0.1:8000/admin/'
        ))