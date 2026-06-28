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
    is_approved = models.BooleanField(default=False)  # ADD THIS LINE - For collector approval
    last_login = models.DateTimeField(blank=True, null=True)

    # Unique Farmer Number — auto-generated when role='farmer'
    farmer_number = models.CharField(max_length=50, blank=True, null=True, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def save(self, *args, **kwargs):
        # Generate farmer_number once, only when role is farmer and number not yet set
        if self.role == 'farmer' and not self.farmer_number:
            from django.utils import timezone
            import uuid
            year = timezone.now().year

            for _ in range(10):
                farmer_count = UserProfile.objects.filter(
                    role='farmer',
                    farmer_number__startswith=f'FRM-{year}-'
                ).count()
                candidate = f'FRM-{year}-{str(farmer_count + 1).zfill(4)}'
                if not UserProfile.objects.filter(farmer_number=candidate).exists():
                    self.farmer_number = candidate
                    break
            else:
                # UUID fallback guarantees uniqueness if sequential slots are exhausted
                self.farmer_number = f'FRM-{year}-{uuid.uuid4().hex[:6].upper()}'

        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a bare UserProfile when a new User is first saved."""
    if created:
        UserProfile.objects.create(user=instance)

# NOTE: save_user_profile signal is intentionally ABSENT.
# It caused a double-save on profile which triggered a UNIQUE constraint
# error on farmer_number when two saves raced for the same candidate number.