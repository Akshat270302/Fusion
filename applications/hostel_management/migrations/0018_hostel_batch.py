from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0017_assignment_metadata'),
    ]

    operations = [
        migrations.CreateModel(
            name='HostelBatch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_name', models.CharField(max_length=80)),
                ('academic_session', models.CharField(max_length=60)),
                ('document_url', models.URLField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.User')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_batches', to='hostel_management.Hall')),
            ],
            options={
                'db_table': 'hostel_management_hostelbatch',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='hostelbatch',
            constraint=models.UniqueConstraint(fields=('hall', 'batch_name', 'academic_session'), name='unique_hostel_batch_per_session'),
        ),
    ]
