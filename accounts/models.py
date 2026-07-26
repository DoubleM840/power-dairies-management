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
    is_approved = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    farmer_number = models.CharField(max_length=50, blank=True, null=True, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def save(self, *args, **kwargs):
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
                self.farmer_number = f'FRM-{year}-{uuid.uuid4().hex[:6].upper()}'

        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


# ==================== NEW CHAT HISTORY MODELS ====================

class ChatSession(models.Model):
    """Store chat sessions for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=200, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ChatMessage(models.Model):
    """Store individual chat messages"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20)  # 'user' or 'assistant'
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"