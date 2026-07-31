from django.db import models


class ReadmeGeneration(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    repo_url = models.CharField(max_length=255, help_text="Repository URL or project name")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    generated_markdown = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.repo_url} - {self.status}"
