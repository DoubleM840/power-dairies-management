from django.core.management.base import BaseCommand
from farmer_app.models import Feed
import os
from django.core.files.base import ContentFile
from PIL import Image
import io

class Command(BaseCommand):
    help = 'Add sample feeds with placeholder images'

    def create_placeholder_image(self, color, text):
        """Create a simple placeholder image"""
        img = Image.new('RGB', (400, 300), color=color)
        return img

    def handle(self, *args, **kwargs):
        feeds_data = [
            {
                'name': 'Dairy Meal Premium',
                'description': 'High-quality dairy meal formulated for maximum milk production. Contains essential proteins, vitamins, and minerals.',
                'price': 2500,
                'stock_quantity': 500,
                'unit': 'kg',
                'low_stock_threshold': 100,
                'color': '#8B4513',  # Brown
                'text': 'Dairy Meal'
            },
            {
                'name': 'Mineral Supplement',
                'description': 'Essential mineral supplement for cow health and immunity. Prevents deficiencies and improves overall well-being.',
                'price': 1500,
                'stock_quantity': 200,
                'unit': 'kg',
                'low_stock_threshold': 50,
                'color': '#2E8B57',  # Green
                'text': 'Minerals'
            },
            {
                'name': 'Hay Bales Premium',
                'description': 'Premium quality dry grass hay bales. Excellent source of roughage for healthy digestion.',
                'price': 800,
                'stock_quantity': 300,
                'unit': 'bale',
                'low_stock_threshold': 75,
                'color': '#DAA520',  # Goldenrod
                'text': 'Hay Bales'
            },
            {
                'name': 'Silage (Maize)',
                'description': 'Fermented green maize fodder. High-energy feed for lactating cows.',
                'price': 1200,
                'stock_quantity': 400,
                'unit': 'kg',
                'low_stock_threshold': 80,
                'color': '#228B22',  # Forest Green
                'text': 'Silage'
            },
            {
                'name': 'Cotton Seed Cake',
                'description': 'Protein-rich cotton seed cake supplement. Boosts milk protein content and overall nutrition.',
                'price': 3000,
                'stock_quantity': 150,
                'unit': 'kg',
                'low_stock_threshold': 40,
                'color': '#8B7355',  # Burlywood
                'text': 'Cotton Cake'
            },
            {
                'name': 'Sunflower Cake',
                'description': 'Sunflower seed cake supplement. Rich in protein and healthy fats for optimal milk production.',
                'price': 2800,
                'stock_quantity': 100,
                'unit': 'kg',
                'low_stock_threshold': 30,
                'color': '#FFD700',  # Gold
                'text': 'Sunflower'
            },
            {
                'name': 'Maize Germ',
                'description': 'Energy-rich maize germ. Excellent for weight gain and milk production.',
                'price': 2200,
                'stock_quantity': 250,
                'unit': 'kg',
                'low_stock_threshold': 60,
                'color': '#FFA500',  # Orange
                'text': 'Maize Germ'
            },
            {
                'name': 'Vitamin Booster',
                'description': 'Complete vitamin supplement for cows. Improves immunity, reproduction, and milk quality.',
                'price': 1800,
                'stock_quantity': 80,
                'unit': 'kg',
                'low_stock_threshold': 20,
                'color': '#4169E1',  # Royal Blue
                'text': 'Vitamins'
            },
            {
                'name': 'Molasses',
                'description': 'Sweet molasses feed additive. Improves palatability and provides quick energy.',
                'price': 900,
                'stock_quantity': 180,
                'unit': 'liter',
                'low_stock_threshold': 50,
                'color': '#8B0000',  # Dark Red
                'text': 'Molasses'
            },
            {
                'name': 'Protein Concentrate',
                'description': 'High-protein concentrate feed. Essential for lactating cows and growing heifers.',
                'price': 3500,
                'stock_quantity': 120,
                'unit': 'kg',
                'low_stock_threshold': 35,
                'color': '#CD853F',  # Peru
                'text': 'Protein'
            },
        ]

        created_count = 0
        updated_count = 0

        for feed_data in feeds_data:
            # Create placeholder image
            img = self.create_placeholder_image(feed_data['color'], feed_data['text'])
            img_io = io.BytesIO()
            img.save(img_io, format='JPEG', quality=95)
            img_io.seek(0)
            
            feed, created = Feed.objects.update_or_create(
                name=feed_data['name'],
                defaults={
                    'description': feed_data['description'],
                    'price': feed_data['price'],
                    'stock_quantity': feed_data['stock_quantity'],
                    'unit': feed_data['unit'],
                    'low_stock_threshold': feed_data['low_stock_threshold'],
                    'is_active': True,
                }
            )
            
            # Save image
            from django.core.files.uploadedfile import SimpleUploadedFile
            image_file = SimpleUploadedFile(
                f"{feed_data['name'].lower().replace(' ', '_')}.jpg",
                img_io.read(),
                content_type='image/jpeg'
            )
            feed.image.save(image_file.name, image_file, save=True)
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Created: {feed.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'🔄 Updated: {feed.name}'))

        self.stdout.write(self.style.SUCCESS(f'\n📦 Total: {created_count} created, {updated_count} updated'))
        self.stdout.write(self.style.SUCCESS('🎨 All feeds now have placeholder images!'))