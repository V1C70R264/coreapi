# Generated manually for OAuth / Google Sign-In fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='auth_provider',
            field=models.CharField(
                choices=[
                    ('email', 'Email'),
                    ('google', 'Google'),
                    ('apple', 'Apple'),
                    ('facebook', 'Facebook'),
                    ('github', 'GitHub'),
                ],
                db_index=True,
                default='email',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='google_sub',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='user',
            name='last_login_provider',
            field=models.CharField(blank=True, db_index=True, default='', max_length=32),
        ),
    ]
