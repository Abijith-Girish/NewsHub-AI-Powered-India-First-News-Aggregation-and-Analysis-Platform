from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='articleinteraction',
            name='duration_seconds',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='articleinteraction',
            name='interaction_type',
            field=models.CharField(
                choices=[('view', 'View'), ('save', 'Save'), ('click', 'Outbound click'), ('search', 'Search'), ('read_time', 'Reading time')],
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name='TrackedClaim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('claim', models.TextField()),
                ('status', models.CharField(choices=[('tracking', 'Tracking'), ('paused', 'Paused')], default='tracking', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('article', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tracked_claims', to='news.article')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracked_claims', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.AddIndex(
            model_name='trackedclaim',
            index=models.Index(fields=['user', '-updated_at'], name='news_tracked_user_updated'),
        ),
        migrations.CreateModel(
            name='ClaimEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evidence_type', models.CharField(choices=[('support', 'Potentially supporting'), ('contradict', 'Potentially contradicting'), ('context', 'Related context')], default='context', max_length=12)),
                ('relevance_score', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='claim_evidence', to='news.article')),
                ('tracked_claim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidence', to='news.trackedclaim')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.AddConstraint(
            model_name='claimevidence',
            constraint=models.UniqueConstraint(fields=('tracked_claim', 'article'), name='unique_claim_article_evidence'),
        ),
    ]
