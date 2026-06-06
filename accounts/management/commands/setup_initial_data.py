from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Creates demo farmer account and ensures admin profile exists'

    def handle(self, *args, **kwargs):
        # 1. Create demo farmer
        if not User.objects.filter(username='demo_farmer').exists():
            user = User.objects.create_user(
                username='demo_farmer',
                email='demo@powerdairies.com',
                password='demo123',
                first_name='Demo',
                last_name='Farmer',
                is_active=True,
            )
            profile = user.profile
            profile.role = 'farmer'
            profile.phone = '+254700000000'
            profile.address = 'Demo Farm, Nairobi'
            profile.save()
            self.stdout.write(self.style.SUCCESS(
                f'Demo farmer created: demo_farmer / demo123 (Farmer ID: {profile.farmer_number})'
            ))
        else:
            self.stdout.write('Demo farmer already exists.')

        # 2. Fix any superuser with no profile or wrong role
        for admin_user in User.objects.filter(is_superuser=True):
            profile, created = UserProfile.objects.get_or_create(user=admin_user)
            if profile.role != 'admin':
                profile.role = 'admin'
                profile.is_active_account = True
                profile.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Fixed admin profile for: {admin_user.username}'
                ))
            else:
                self.stdout.write(f'Admin profile OK for: {admin_user.username}')

        self.stdout.write(self.style.SUCCESS('Setup complete!'))