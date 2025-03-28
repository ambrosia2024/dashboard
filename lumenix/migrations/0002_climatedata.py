# Generated by Django 5.1.7 on 2025-03-19 23:59

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lumenix', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClimateData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.SmallIntegerField(choices=[(1, 'Active'), (0, 'Inactive'), (2, 'Deleted')], default=1, verbose_name='Status')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('timestamp', models.DateTimeField(verbose_name='Timestamp')),
                ('latitude', models.FloatField(validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)], verbose_name='Latitude')),
                ('longitude', models.FloatField(validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name='Longitude')),
                ('temperature', models.FloatField(verbose_name='Temperature (°C)')),
            ],
            options={
                'verbose_name': 'Climate Data',
                'verbose_name_plural': 'Climate Data Records',
                'db_table': 'climate_data',
                'indexes': [models.Index(fields=['timestamp'], name='climate_dat_timesta_c66692_idx'), models.Index(fields=['latitude', 'longitude'], name='climate_dat_latitud_0b35a8_idx')],
            },
        ),
    ]
