from django.core.management.base import BaseCommand
from farmer_app.models import Feed
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import io
import os

class Command(BaseCommand):
    help = 'Add premium feeds with professional images'

    def create_professional_image(self, feed_name, category, price):
        """Create a professional-looking product image"""
        # Create image with gradient background
        img = Image.new('RGB', (600, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        # Define colors based on category
        colors = {
            'Energy Feeds': ('#FF8C00', '#FFA500'),  # Orange gradient
            'Protein Feeds': ('#8B4513', '#A0522D'),  # Brown gradient
            'Roughage': ('#228B22', '#32CD32'),  # Green gradient
            'Supplements': ('#4169E1', '#6495ED'),  # Blue gradient
            'Minerals': ('#DC143C', '#FF6347'),  # Red gradient
            'Vitamins': ('#9370DB', '#BA55D3'),  # Purple gradient
        }
        
        color1, color2 = colors.get(category, ('#708090', '#A9A9A9'))
        
        # Draw gradient background
        for y in range(400):
            r = int(int(color1[1:3], 16) + (int(color2[1:3], 16) - int(color1[1:3], 16)) * y / 400)
            g = int(int(color1[3:5], 16) + (int(color2[3:5], 16) - int(color1[3:5], 16)) * y / 400)
            b = int(int(color1[5:7], 16) + (int(color2[5:7], 16) - int(color1[5:7], 16)) * y / 400)
            draw.rectangle([(0, y), (600, y+1)], fill=(r, g, b))
        
        # Draw product badge
        draw.rounded_rectangle([(50, 50), (550, 350)], radius=20, fill='white')
        
        # Add text
        try:
            # Try to use a bold font
            font_large = ImageFont.truetype("arialbd.ttf", 36)
            font_medium = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 18)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Draw category badge
        draw.rounded_rectangle([(50, 50), (250, 90)], radius=10, fill=color1)
        draw.text((150, 62), category, fill='white', font=font_small, anchor='mm')
        
        # Draw product name
        draw.text((300, 150), feed_name, fill='#2C3E50', font=font_large, anchor='mm')
        
        # Draw price
        draw.text((300, 220), f'KES {price}', fill='#27AE60', font=font_medium, anchor='mm')
        
        # Draw "Power Dairies" branding
        draw.text((300, 310), 'POWER DAIRIES', fill='#7F8C8D', font=font_small, anchor='mm')
        
        # Add cow icon (simple representation)
        draw.ellipse([(80, 120), (120, 160)], fill=color1)
        draw.rectangle([(90, 160), (110, 200)], fill=color1)
        
        return img

    def handle(self, *args, **kwargs):
        # Comprehensive feed catalog
        feeds_data = [
            # ENERGY FEEDS
            {
                'name': 'Dairy Meal Premium',
                'category': 'Energy Feeds',
                'description': 'High-energy dairy meal formulated for maximum milk production. Contains 16% crude protein with balanced vitamins and minerals.',
                'price': 2500,
                'stock_quantity': 500,
                'unit': 'kg',
                'nutritional_info': 'CP: 16%, TDN: 75%, Fiber: 12%'
            },
            {
                'name': 'Maize Germ Meal',
                'category': 'Energy Feeds',
                'description': 'Energy-rich maize germ byproduct. Excellent for weight gain and boosting milk butterfat content.',
                'price': 2200,
                'stock_quantity': 300,
                'unit': 'kg',
                'nutritional_info': 'CP: 21%, Oil: 8%, TDN: 80%'
            },
            {
                'name': 'Wheat Bran',
                'category': 'Energy Feeds',
                'description': 'Highly digestible wheat bran. Great source of energy and phosphorus for lactating cows.',
                'price': 1800,
                'stock_quantity': 400,
                'unit': 'kg',
                'nutritional_info': 'CP: 15%, Fiber: 10%, Phosphorus: 1.2%'
            },
            {
                'name': 'Molasses Feed Grade',
                'category': 'Energy Feeds',
                'description': 'Sweet molasses additive. Improves feed palatability and provides quick energy. Mix with roughage.',
                'price': 900,
                'stock_quantity': 200,
                'unit': 'liter',
                'nutritional_info': 'Sugar: 50%, Energy: 2800 kcal/kg'
            },
            
            # PROTEIN FEEDS
            {
                'name': 'Cotton Seed Cake',
                'category': 'Protein Feeds',
                'description': 'Premium protein-rich cotton seed cake. Boosts milk protein content and overall nutrition.',
                'price': 3000,
                'stock_quantity': 250,
                'unit': 'kg',
                'nutritional_info': 'CP: 41%, Fat: 12%, Fiber: 15%'
            },
            {
                'name': 'Sunflower Cake',
                'category': 'Protein Feeds',
                'description': 'High-quality sunflower seed cake. Rich in protein and healthy fats for optimal milk production.',
                'price': 2800,
                'stock_quantity': 180,
                'unit': 'kg',
                'nutritional_info': 'CP: 35%, Fat: 10%, Fiber: 18%'
            },
            {
                'name': 'Soybean Meal',
                'category': 'Protein Feeds',
                'description': 'Premium soybean meal with 44% protein. Best protein source for high-yielding dairy cows.',
                'price': 3500,
                'stock_quantity': 150,
                'unit': 'kg',
                'nutritional_info': 'CP: 44%, Lysine: 2.8%, Methionine: 0.6%'
            },
            {
                'name': 'Fish Meal (Imported)',
                'category': 'Protein Feeds',
                'description': 'High-quality fish meal. Excellent protein source with essential amino acids and omega-3.',
                'price': 4500,
                'stock_quantity': 80,
                'unit': 'kg',
                'nutritional_info': 'CP: 65%, Fat: 10%, Omega-3: 2%'
            },
            
            # ROUGHAGE
            {
                'name': 'Premium Hay Bales',
                'category': 'Roughage',
                'description': 'Premium quality Rhodes grass hay bales. Excellent source of roughage for healthy rumen function.',
                'price': 800,
                'stock_quantity': 500,
                'unit': 'bale',
                'nutritional_info': 'CP: 8%, Fiber: 35%, Weight: 20kg/bale'
            },
            {
                'name': 'Maize Silage',
                'category': 'Roughage',
                'description': 'Fermented green maize fodder. High-energy silage for lactating cows. Moisture content 65%.',
                'price': 1200,
                'stock_quantity': 1000,
                'unit': 'kg',
                'nutritional_info': 'CP: 8%, TDN: 70%, pH: 4.0'
            },
            {
                'name': 'Napier Grass (Fresh)',
                'category': 'Roughage',
                'description': 'Fresh cut Napier grass. High-yielding fodder grass, best fed with protein supplements.',
                'price': 150,
                'stock_quantity': 2000,
                'unit': 'bundle',
                'nutritional_info': 'CP: 10%, Fiber: 30%, Weight: 5kg/bundle'
            },
            {
                'name': 'Lucerne Hay',
                'category': 'Roughage',
                'description': 'Premium lucerne (alfalfa) hay. High protein roughage, excellent for milk production.',
                'price': 1500,
                'stock_quantity': 200,
                'unit': 'kg',
                'nutritional_info': 'CP: 18%, Calcium: 1.5%, Fiber: 28%'
            },
            
            # SUPPLEMENTS
            {
                'name': 'Mineral Premix Dairy',
                'category': 'Supplements',
                'description': 'Complete mineral premix for dairy cows. Contains calcium, phosphorus, magnesium, and trace minerals.',
                'price': 1500,
                'stock_quantity': 150,
                'unit': 'kg',
                'nutritional_info': 'Ca: 18%, P: 10%, Mg: 5%, Zn: 3000ppm'
            },
            {
                'name': 'Vitamin ADE Complex',
                'category': 'Supplements',
                'description': 'Complete vitamin supplement. Improves immunity, reproduction, and milk quality.',
                'price': 2200,
                'stock_quantity': 100,
                'unit': 'kg',
                'nutritional_info': 'Vit A: 500,000 IU, Vit D3: 100,000 IU, Vit E: 500 IU'
            },
            {
                'name': 'Yeast Culture',
                'category': 'Supplements',
                'description': 'Live yeast culture for improved rumen function. Increases fiber digestion and milk yield.',
                'price': 3200,
                'stock_quantity': 60,
                'unit': 'kg',
                'nutritional_info': 'Live Yeast: 10 billion CFU/g'
            },
            {
                'name': 'Buffer Mix (Sodium Bicarbonate)',
                'category': 'Supplements',
                'description': 'Rumen buffer for high-grain diets. Prevents acidosis and maintains milk fat percentage.',
                'price': 1200,
                'stock_quantity': 120,
                'unit': 'kg',
                'nutritional_info': 'NaHCO3: 99%, pH Buffer'
            },
            
            # MINERALS
            {
                'name': 'Calcium Phosphate',
                'category': 'Minerals',
                'description': 'Dicalcium phosphate supplement. Essential for bone development and milk production.',
                'price': 1800,
                'stock_quantity': 100,
                'unit': 'kg',
                'nutritional_info': 'Ca: 23%, P: 18%'
            },
            {
                'name': 'Salt Lick Block',
                'category': 'Minerals',
                'description': 'Mineralized salt lick block. Provides essential minerals and encourages water intake.',
                'price': 450,
                'stock_quantity': 200,
                'unit': 'piece',
                'nutritional_info': 'NaCl: 95%, Minerals: 5%, Weight: 5kg'
            },
            {
                'name': 'Magnesium Oxide',
                'category': 'Minerals',
                'description': 'Magnesium supplement to prevent grass tetany. Essential for lactating cows on lush pasture.',
                'price': 1600,
                'stock_quantity': 80,
                'unit': 'kg',
                'nutritional_info': 'Mg: 60%, Prevents hypomagnesemia'
            },
        ]

        created_count = 0
        updated_count = 0

        self.stdout.write(self.style.SUCCESS('\n🎨 Creating professional feed images and adding products...\n'))

        for feed_data in feeds_data:
            # Create professional image
            img = self.create_professional_image(
                feed_data['name'],
                feed_data['category'],
                feed_data['price']
            )
            
            # Convert to Django file
            img_io = io.BytesIO()
            img.save(img_io, format='JPEG', quality=95)
            img_io.seek(0)
            
            from django.core.files.uploadedfile import SimpleUploadedFile
            image_file = SimpleUploadedFile(
                f"{feed_data['name'].lower().replace(' ', '_')}.jpg",
                img_io.read(),
                content_type='image/jpeg'
            )
            
            # Create or update feed
            feed, created = Feed.objects.update_or_create(
                name=feed_data['name'],
                defaults={
                    'description': f"{feed_data['description']}\n\nNutritional Info: {feed_data['nutritional_info']}",
                    'price': feed_data['price'],
                    'stock_quantity': feed_data['stock_quantity'],
                    'unit': feed_data['unit'],
                    'low_stock_threshold': feed_data['stock_quantity'] // 5,  # 20% threshold
                    'is_active': True,
                }
            )
            
            # Save image
            feed.image.save(image_file.name, image_file, save=True)
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ {feed.name} - KES {feed.price}/{feed.unit}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'🔄 Updated: {feed.name}'))

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'📦 TOTAL: {created_count} created, {updated_count} updated'))
        self.stdout.write(self.style.SUCCESS(f'🎨 All feeds now have professional images!'))
        self.stdout.write(self.style.SUCCESS(f'📊 Categories: Energy, Protein, Roughage, Supplements, Minerals'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))