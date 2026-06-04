from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create admin superuser'

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@powerdairies.co.ke',
                password='admin123',
                first_name='System',
                last_name='Administrator',
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(self.style.SUCCESS('✅ Admin user created successfully!'))
            self.stdout.write(self.style.WARNING('Username: admin'))
            self.stdout.write(self.style.WARNING('Password: admin123'))
        else:
            self.stdout.write(self.style.SUCCESS('Admin user already exists!'))