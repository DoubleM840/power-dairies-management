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
    
    # Unique Farmer Number
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
            from django.utils import timezone
            year = timezone.now().year
            
            # Keep trying until we find a unique number
            attempt = 1
            while attempt <= 1000:  # Safety limit
                # Count existing farmers this year
                farmer_count = UserProfile.objects.filter(
                    role='farmer', 
                    farmer_number__startswith=f'FRM-{year}-'
                ).count()
                
                # Generate candidate number
                new_num = str(farmer_count + attempt).zfill(4)
                candidate_number = f'FRM-{year}-{new_num}'
                
                # Check if this number already exists
                if not UserProfile.objects.filter(farmer_number=candidate_number).exists():
                    self.farmer_number = candidate_number
                    break
                
                # Try next number
                attempt += 1
            
            # If we couldn't find a unique number after 1000 attempts
            if attempt > 1000:
                raise Exception("Could not generate unique farmer number after 1000 attempts")
        
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


def save(self, *args, **kwargs):
    # Only generate farmer number if it doesn't exist and user is a farmer
    if self.role == 'farmer' and not self.farmer_number and self.pk:
        from django.utils import timezone
        import time
        
        # Use timestamp + user ID to guarantee uniqueness
        now = timezone.now()
        timestamp = now.strftime('%H%M%S%f')  # Hour-Minute-Second-Microsecond
        user_id = self.user.id if self.user.id else 1
        
        # Format: FRM-2026-130415123456 (year + timestamp)
        self.farmer_number = f'FRM-{now.year}-{timestamp}{user_id}'
    
    super().save(*args, **kwargs)