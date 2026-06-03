from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# ==================== USER PROFILE ====================
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('collector', 'Collector'),
        ('farmer', 'Farmer'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='farmer')
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

# ==================== COW/LIVESTOCK ====================
class Cow(models.Model):
    BREED_CHOICES = (
        ('Friesian', 'Friesian'),
        ('Jersey', 'Jersey'),
        ('Ayrshire', 'Ayrshire'),
        ('Guernsey', 'Guernsey'),
        ('Sahiwal', 'Sahiwal'),
        ('Ankole', 'Ankole'),
        ('Crossbreed', 'Crossbreed'),
    )
    HEALTH_STATUS = (
        ('Healthy', 'Healthy'),
        ('Sick', 'Sick'),
        ('Under Treatment', 'Under Treatment'),
        ('Recovered', 'Recovered'),
    )
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cows')
    tag = models.CharField(max_length=20)
    breed_type = models.CharField(max_length=20, choices=BREED_CHOICES, default='Friesian')
    name = models.CharField(max_length=50, blank=True, null=True)
    age_months = models.IntegerField(default=12)
    health_status = models.CharField(max_length=20, choices=HEALTH_STATUS, default='Healthy')
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('farmer', 'tag')

    def __str__(self):
        return f"{self.name or 'Cow'} - {self.tag} ({self.breed_type})"


# ==================== HEALTH HISTORY ====================
class HealthRecord(models.Model):
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='health_records')
    date = models.DateField()
    description = models.TextField()
    treatment = models.TextField(blank=True, null=True)
    vet_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Health Record for {self.cow.tag} on {self.date}"


# ==================== MILK RECORD ====================
class MilkRecord(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='milk_records')
    collector = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='collected_records')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # in liters
    fat_content = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # percentage
    date_collected = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.farmer.username} - {self.quantity}L on {self.date_collected}"


# ==================== RATES ====================
class Rate(models.Model):
    fat_rate = models.DecimalField(max_digits=10, decimal_places=2, default=50)  # per liter per fat %
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)  # percentage
    effective_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Rate: {self.fat_rate}/L at {self.fat_content}% fat - Effective {self.effective_date}"


# ==================== PAYMENT ====================
class Payment(models.Model):
    PAYMENT_TYPE = (
        ('milk_sale', 'Milk Sale'),
        ('feed_order', 'Feed Order'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    method = models.CharField(max_length=50, blank=True, null=True)  # M-Pesa, Milk Deduction
    description = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_approved = models.DateTimeField(blank=True, null=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.status})"


# ==================== FEED ====================
class Feed(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)  # in kg
    low_stock_threshold = models.IntegerField(default=50)
    unit = models.CharField(max_length=20, default='kg')
    image = models.ImageField(upload_to='feeds/', blank=True, null=True)  # ✅ Make sure this exists
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold


# ==================== FEED ORDER ====================
class FeedOrder(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Processing', 'Processing'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    )
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feed_orders')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='orders')
    quantity = models.IntegerField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.farmer.username} - {self.feed.name} x{self.quantity}"


# ==================== CART ====================
class Cart(models.Model):
    farmer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.farmer.username}"

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.feed.price * self.quantity

    def __str__(self):
        return f"{self.feed.name} x{self.quantity}"


# ==================== CLAIM ====================
class Claim(models.Model):
    CATEGORY_CHOICES = (
        ('payment', 'Payment Issue'),
        ('collector', 'Collector Complaint'),
        ('system', 'System Bug'),
        ('other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Under Review', 'Under Review'),
        ('Resolved', 'Resolved'),
        ('Rejected', 'Rejected'),
    )
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='claims')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    admin_response = models.TextField(blank=True, null=True)
    date_filed = models.DateTimeField(auto_now_add=True)
    date_resolved = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Claim #{self.id} by {self.farmer.username} - {self.subject}"


# ==================== NOTIFICATION ====================
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.title}"


# ==================== COLLECTOR ALLOCATION ====================
class CollectorAllocation(models.Model):
    collector = models.ForeignKey(User, on_delete=models.CASCADE, related_name='allocations')
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collector_allocations')
    area = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    date_assigned = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('collector', 'farmer')

    def __str__(self):
        return f"{self.collector.username} -> {self.farmer.username} ({self.area})"