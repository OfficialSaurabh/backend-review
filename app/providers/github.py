import httpx

class GitHubProvider:
    API = "https://api.github.com"

    def __init__(self, token: str | None = None):
        if token:
            self.headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        else:
            self.headers = {
                "Accept": "application/vnd.github+json",
            }

    async def get_file_content(self, owner, repo, ref, path):
        url = f"{self.API}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json()

    async def get_repo_tree(self, owner, repo, ref):
        url = f"{self.API}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json()["tree"]
