import httpx

class BitbucketProvider:
    API = "https://api.bitbucket.org/2.0"

    def __init__(self, access_token: str):
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def get_file_content(self, workspace, repo, ref, path):
        clean_path = path.lstrip("/")
        url = f"{self.API}/repositories/{workspace}/{repo}/src/{ref}/{clean_path}"

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            return r.text

    async def get_repo_tree(self, workspace, repo, ref):
        url = f"{self.API}/repositories/{workspace}/{repo}/src/{ref}/"

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            data = r.json()

            return [
                {"path": f["path"], "type": "blob" if f["type"] == "commit_file" else "tree"}
                for f in data["values"]
            ]
