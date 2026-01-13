from app.providers.github import GitHubProvider
from app.providers.bitbucket import BitbucketProvider

def get_provider(provider: str, token: str):
    if provider == "github":
        return GitHubProvider(token)
    elif provider == "bitbucket":
        return BitbucketProvider(token)
