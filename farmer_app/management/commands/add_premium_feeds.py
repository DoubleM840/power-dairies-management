from django.core.management.base import BaseCommand
from farmer_app.models import Feed
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


class Command(BaseCommand):
    help = 'Add premium feeds with professional images'

    def create_professional_image(self, feed_name, category, price):
        """Create a professional-looking product image"""
        img = Image.new('RGB', (600, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        colors = {
            'Energy Feeds': ('#FF8C00', '#FFA500'),
            'Protein Feeds': ('#8B4513', '#A0522D'),
            'Roughage': ('#228B22', '#32CD32'),
            'Supplements': ('#4169E1', '#6495ED'),
            'Minerals': ('#DC143C', '#FF6347'),
            'Vitamins': ('#9370DB', '#BA55D3'),
        }
        
        color1, color2 = colors.get(category, ('#708090', '#A9A9A9'))
        
        for y in range(400):
            r = int(int(color1[1:3], 16) + (int(color2[1:3], 16) - int(color1[1:3], 16)) * y / 400)
            g = int(int(color1[3:5], 16) + (int(color2[3:5], 16) - int(color1[3:5], 16)) * y / 400)
            b = int(int(color1[5:7], 16) + (int(color2[5:7], 16) - int(color1[5:7], 16)) * y / 400)
            draw.rectangle([(0, y), (600, y+1)], fill=(r, g, b))
        
        draw.rounded_rectangle([(50, 50), (550, 350)], radius=20, fill='white')
        
        try:
            font_large = ImageFont.truetype("arialbd.ttf", 36)
            font_medium = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 18)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        draw.rounded_rectangle([(50, 50), (250, 90)], radius=10, fill=color1)
        draw.text((150, 62), category, fill='white', font=font_small, anchor='mm')
        draw.text((300, 150), feed_name, fill='#2C3E50', font=font_large, anchor='mm')
        draw.text((300, 220), f'KES {price}', fill='#27AE60', font=font_medium, anchor='mm')
        draw.text((300, 310), 'POWER DAIRIES', fill='#7F8C8D', font=font_small, anchor='mm')
        draw.ellipse([(80, 120), (120, 160)], fill=color1)
        draw.rectangle([(90, 160), (110, 200)], fill=color1)
        
        return img

    def handle(self, *args, **kwargs):
        feeds_data = [
            {'name': 'Dairy Meal Premium', 'category': 'Energy Feeds', 'description': 'High-energy dairy meal for maximum milk production.', 'price': 2500, 'stock_quantity': 500, 'unit': 'kg'},
            {'name': 'Maize Germ Meal', 'category': 'Energy Feeds', 'description': 'Energy-rich maize germ byproduct.', 'price': 2200, 'stock_quantity': 300, 'unit': 'kg'},
            {'name': 'Wheat Bran', 'category': 'Energy Feeds', 'description': 'Highly digestible wheat bran.', 'price': 1800, 'stock_quantity': 400, 'unit': 'kg'},
            {'name': 'Molasses Feed Grade', 'category': 'Energy Feeds', 'description': 'Sweet molasses for quick energy.', 'price': 900, 'stock_quantity': 200, 'unit': 'liter'},
            {'name': 'Cotton Seed Cake', 'category': 'Protein Feeds', 'description': 'Premium protein-rich cotton seed cake.', 'price': 3000, 'stock_quantity': 250, 'unit': 'kg'},
            {'name': 'Sunflower Cake', 'category': 'Protein Feeds', 'description': 'High-quality sunflower seed cake.', 'price': 2800, 'stock_quantity': 180, 'unit': 'kg'},
            {'name': 'Soybean Meal', 'category': 'Protein Feeds', 'description': 'Premium soybean meal with 44% protein.', 'price': 3500, 'stock_quantity': 150, 'unit': 'kg'},
            {'name': 'Fish Meal Imported', 'category': 'Protein Feeds', 'description': 'High-quality fish meal.', 'price': 4500, 'stock_quantity': 80, 'unit': 'kg'},
            {'name': 'Premium Hay Bales', 'category': 'Roughage', 'description': 'Premium quality Rhodes grass hay.', 'price': 800, 'stock_quantity': 500, 'unit': 'bale'},
            {'name': 'Maize Silage', 'category': 'Roughage', 'description': 'Fermented green maize fodder.', 'price': 1200, 'stock_quantity': 1000, 'unit': 'kg'},
            {'name': 'Napier Grass Fresh', 'category': 'Roughage', 'description': 'Fresh cut Napier grass.', 'price': 150, 'stock_quantity': 2000, 'unit': 'bundle'},
            {'name': 'Lucerne Hay', 'category': 'Roughage', 'description': 'Premium lucerne hay.', 'price': 1500, 'stock_quantity': 200, 'unit': 'kg'},
            {'name': 'Mineral Premix Dairy', 'category': 'Supplements', 'description': 'Complete mineral premix.', 'price': 1500, 'stock_quantity': 150, 'unit': 'kg'},
            {'name': 'Vitamin ADE Complex', 'category': 'Supplements', 'description': 'Complete vitamin supplement.', 'price': 2200, 'stock_quantity': 100, 'unit': 'kg'},
            {'name': 'Yeast Culture', 'category': 'Supplements', 'description': 'Live yeast culture.', 'price': 3200, 'stock_quantity': 60, 'unit': 'kg'},
            {'name': 'Buffer Mix Sodium Bicarbonate', 'category': 'Supplements', 'description': 'Rumen buffer.', 'price': 1200, 'stock_quantity': 120, 'unit': 'kg'},
            {'name': 'Calcium Phosphate', 'category': 'Minerals', 'description': 'Dicalcium phosphate.', 'price': 1800, 'stock_quantity': 100, 'unit': 'kg'},
            {'name': 'Salt Lick Block', 'category': 'Minerals', 'description': 'Mineralized salt lick block.', 'price': 450, 'stock_quantity': 200, 'unit': 'piece'},
            {'name': 'Magnesium Oxide', 'category': 'Minerals', 'description': 'Magnesium supplement.', 'price': 1600, 'stock_quantity': 80, 'unit': 'kg'},
        ]

        created_count = 0
        updated_count = 0

        self.stdout.write(self.style.SUCCESS('\n🎨 Creating professional feed images...\n'))

        for feed_data in feeds_data:
            img = self.create_professional_image(
                feed_data['name'],
                feed_data['category'],
                feed_data['price']
            )
            
            filename = f"{feed_data['name'].lower().replace(' ', '_')}.jpg"
            
            static_feeds_dir = Path('static/feeds')
            static_feeds_dir.mkdir(parents=True, exist_ok=True)
            
            image_path = static_feeds_dir / filename
            img.save(image_path, format='JPEG', quality=95)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Generated: {filename}'))
            
            feed, created = Feed.objects.update_or_create(
                name=feed_data['name'],
                defaults={
                    'description': feed_data['description'],
                    'price': feed_data['price'],
                    'stock_quantity': feed_data['stock_quantity'],
                    'unit': feed_data['unit'],
                    'low_stock_threshold': feed_data['stock_quantity'] // 5,
                    'image': f'feeds/{filename}',
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'✅ {created_count} created, {updated_count} updated'))
        self.stdout.write(self.style.SUCCESS(f'📁 Images saved to static/feeds/'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))