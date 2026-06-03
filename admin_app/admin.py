from django.contrib import admin
from farmer_app.models import (
    UserProfile, Cow, HealthRecord, MilkRecord, Rate, Payment,
    Feed, FeedOrder, Cart, CartItem, Claim, Notification, CollectorAllocation
)

admin.site.register(UserProfile)
admin.site.register(Cow)
admin.site.register(HealthRecord)
admin.site.register(MilkRecord)
admin.site.register(Rate)
admin.site.register(Payment)
admin.site.register(Feed)
admin.site.register(FeedOrder)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Claim)
admin.site.register(Notification)
admin.site.register(CollectorAllocation)