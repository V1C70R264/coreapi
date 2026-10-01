from django.db import models


class Promotion(models.Model):
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=255)
    cta_label = models.CharField(max_length=50, default='Shop Now')
    image = models.ImageField(upload_to='promotions/')

    # Hex color matching the uploaded image's own backdrop, so the card
    # background and the photo blend seamlessly with no visible seam —
    # set by whoever uploads the promotion, not hardcoded in the app.
    background_color = models.CharField(
        max_length=7,
        default='#F5E6C8',
        help_text="Hex color matching the image's background, e.g. #F5E6C8",
    )

    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return self.title
