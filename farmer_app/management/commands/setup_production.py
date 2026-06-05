from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile
from farmer_app.models import Feed, Cow

class Command(BaseCommand):
    help = 'Sets up production database with Admin, Demo User, and Sample Data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🚀 Starting Production Setup...'))

        # 1. Setup Admin
        self.stdout.write('Setting up Admin...')
        User.objects.filter(username='admin').delete()
        admin = User.objects.create_superuser('admin', 'admin@powerdairies.com', 'admin123')
        admin.profile.role = 'admin'
        admin.profile.is_active_account = True
        admin.profile.save()
        self.stdout.write(self.style.SUCCESS('✅ Admin created (admin / admin123)'))

        # 2. Setup Demo Farmer
        self.stdout.write('Setting up Demo Farmer...')
        User.objects.filter(username='demo_farmer').delete()
        demo = User.objects.create_user('demo_farmer', 'demo@powerdairies.com', 'demo123')
        demo.profile.role = 'farmer'
        demo.profile.farmer_number = 'DEMO-2026-0001'
        demo.profile.is_active_account = True
        demo.profile.save()
        self.stdout.write(self.style.SUCCESS('✅ Demo Farmer created (demo_farmer / demo123)'))

        # 3. Add Sample Feeds (Safe to run multiple times)
        self.stdout.write('Adding Sample Feeds...')
        feeds = [
            {'name': 'Dairy Meal Premium', 'price': 3500, 'stock': 150, 'image': 'feeds/dairy_meal_premium.jpg'},
            {'name': 'Salt Lick Block', 'price': 450, 'stock': 120, 'image': 'feeds/salt_lick_block.jpg'},
            {'name': 'Hay Bales', 'price': 450, 'stock': 200, 'image': 'feeds/hay_bales_premium.jpg'},
        ]
        for f in feeds:
            Feed.objects.update_or_create(name=f['name'], defaults={'price': f['price'], 'stock_quantity': f['stock'], 'image': f['image']})
        self.stdout.write(self.style.SUCCESS(f'✅ {len(feeds)} Feeds added/updated'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Setup Complete! You can now login.'))