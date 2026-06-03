from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from farmer_app.models import UserProfile, Feed, Rate, Cow
from datetime import date


class Command(BaseCommand):
    help = 'Setup initial data for Dairy Management System'

    def handle(self, *args, **kwargs):
        # Create Admin
        admin_user, created = User.objects.get_or_create(username='admin')
        if created:
            admin_user.set_password('admin123')
            admin_user.first_name = 'System'
            admin_user.last_name = 'Admin'
            admin_user.email = 'admin@dairy.com'
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            UserProfile.objects.create(user=admin_user, role='admin', phone='0700000000')
            self.stdout.write(self.style.SUCCESS('Admin created: admin/admin123'))
        
        # Create Collector
        collector, created = User.objects.get_or_create(username='collector1')
        if created:
            collector.set_password('collect123')
            collector.first_name = 'John'
            collector.last_name = 'Collector'
            collector.email = 'collector@dairy.com'
            collector.save()
            UserProfile.objects.create(user=collector, role='collector', phone='0711111111')
            self.stdout.write(self.style.SUCCESS('Collector created: collector1/collect123'))
        
        # Create Farmer
        farmer, created = User.objects.get_or_create(username='farmer1')
        if created:
            farmer.set_password('farm123')
            farmer.first_name = 'Mary'
            farmer.last_name = 'Farmer'
            farmer.email = 'farmer@dairy.com'
            farmer.save()
            UserProfile.objects.create(user=farmer, role='farmer', phone='0722222222', address='Zone A, Village 1')
            self.stdout.write(self.style.SUCCESS('Farmer created: farmer1/farm123'))
        
        # Create initial feeds
        feeds_data = [
            {'name': 'Dairy Meal Premium', 'description': 'High-quality dairy meal for milk production', 'price': 2500, 'stock_quantity': 500, 'low_stock_threshold': 100},
            {'name': 'Mineral Supplement', 'description': 'Essential minerals for cow health', 'price': 1500, 'stock_quantity': 200, 'low_stock_threshold': 50},
            {'name': 'Hay Bales', 'description': 'Dry grass hay bales for roughage', 'price': 800, 'stock_quantity': 300, 'low_stock_threshold': 75},
            {'name': 'Silage', 'description': 'Fermented green fodder', 'price': 1200, 'stock_quantity': 400, 'low_stock_threshold': 80},
            {'name': 'Cotton Seed Cake', 'description': 'Protein-rich cotton seed cake', 'price': 3000, 'stock_quantity': 150, 'low_stock_threshold': 40},
            {'name': 'Sunflower Cake', 'description': 'Sunflower seed cake supplement', 'price': 2800, 'stock_quantity': 100, 'low_stock_threshold': 30},
        ]
        for feed_data in feeds_data:
            Feed.objects.get_or_create(name=feed_data['name'], defaults=feed_data)
        self.stdout.write(self.style.SUCCESS('Feeds created'))
        
        # Create initial rate
        Rate.objects.get_or_create(
            effective_date=date.today(),
            defaults={'fat_rate': 50, 'commission_rate': 5, 'is_active': True}
        )
        self.stdout.write(self.style.SUCCESS('Rate created'))
        
        # Create 15 cows for farmer1
        breeds = ['Friesian', 'Jersey', 'Ayrshire', 'Guernsey', 'Sahiwal', 'Ankole', 'Crossbreed']
        cow_names = ['Daisy', 'Bella', 'Rosie', 'Luna', 'Stella', 'Molly', 'Ginger', 'Cocoa', 'Honey', 'Maple', 'Cleo', 'Nala', 'Pearl', 'Ruby', 'Ginger2']
        for i in range(15):
            Cow.objects.get_or_create(
                farmer=farmer,
                tag=f'COW-{str(i+1).zfill(3)}',
                defaults={
                    'name': cow_names[i],
                    'breed_type': breeds[i % len(breeds)],
                    'age_months': 18 + (i * 3),
                    'health_status': 'Healthy'
                }
            )
        self.stdout.write(self.style.SUCCESS('15 cows created for farmer1'))
        
        self.stdout.write(self.style.SUCCESS('\n=== SETUP COMPLETE ==='))
        self.stdout.write(self.style.SUCCESS('Login at /login/'))
        self.stdout.write(self.style.SUCCESS('Admin: admin/admin123'))
        self.stdout.write(self.style.SUCCESS('Collector: collector1/collect123'))
        self.stdout.write(self.style.SUCCESS('Farmer: farmer1/farm123'))