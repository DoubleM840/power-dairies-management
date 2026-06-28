from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile

class Command(BaseCommand):
    help = 'Create profiles for all users that are missing them'

    def handle(self, *args, **kwargs):
        # Find all users who do NOT have a profile
        users_without_profiles = User.objects.filter(profile__isnull=True)
        
        if not users_without_profiles.exists():
            self.stdout.write(self.style.SUCCESS('All users already have profiles!'))
            return

        for user in users_without_profiles:
            # Create the missing profile
            UserProfile.objects.create(user=user, role='farmer', is_approved=True)
            self.stdout.write(self.style.SUCCESS(f'Created profile for: {user.username}'))
        
        self.stdout.write(self.style.SUCCESS('Done! All users now have profiles.'))