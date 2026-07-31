import os
from rest_framework import serializers
from .models import ReadmeGeneration

_DEFAULT_PROVIDER = os.environ.get('AUTOREADME_LLM_PROVIDER', 'groq').lower()




class ReadmeGenerationSerializer(serializers.ModelSerializer):
    markdown = serializers.CharField(source='generated_markdown', read_only=True)
    repo_name = serializers.CharField(source='repo_url', read_only=True)

    class Meta:
        model = ReadmeGeneration
        fields = ['id', 'repo_url', 'repo_name', 'status', 'generated_markdown', 'markdown', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'generated_markdown', 'markdown', 'repo_name', 'created_at', 'updated_at']


class GenerateReadmeRequestSerializer(serializers.Serializer):
    github_url = serializers.CharField(required=False, max_length=255, allow_blank=True)
    repo_url = serializers.CharField(required=False, max_length=255, allow_blank=True)
    provider = serializers.ChoiceField(choices=['gemini', 'gpt', 'claude', 'groq', 'huggingface'], default=_DEFAULT_PROVIDER)


    def validate(self, attrs):
        url = attrs.get('github_url') or attrs.get('repo_url')
        if not url:
            raise serializers.ValidationError({"github_url": "Either github_url or repo_url is required."})
        attrs['url'] = url
        return attrs



