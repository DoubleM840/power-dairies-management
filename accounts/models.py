from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('collector', 'Collector'),
        ('farmer', 'Farmer'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='farmer')
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active_account = models.BooleanField(default=True)
    last_login = models.DateTimeField(blank=True, null=True)
    
    # NEW: Unique Farmer Number
    farmer_number = models.CharField(max_length=20, blank=True, null=True, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def save(self, *args, **kwargs):
        # Auto-generate farmer number if role is farmer and no number exists
        if self.role == 'farmer' and not self.farmer_number:
            # Generate format: FRM-YYYY-XXXX (e.g., FRM-2026-0001)
            from django.utils import timezone
            year = timezone.now().year
            # Get the last farmer and increment
            last_user = UserProfile.objects.filter(
                role='farmer', 
                farmer_number__startswith=f'FRM-{year}-'
            ).order_by('-farmer_number').first()
            
            if last_user:
                # Extract number and increment
                last_num = int(last_user.farmer_number.split('-')[-1])
                new_num = str(last_num + 1).zfill(4)
            else:
                new_num = '0001'
            
            self.farmer_number = f'FRM-{year}-{new_num}'
        
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()