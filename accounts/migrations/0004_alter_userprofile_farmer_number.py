from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_userprofile_farmer_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='farmer_number',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]