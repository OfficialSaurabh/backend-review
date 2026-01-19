class VCSProvider:
    async def get_file_content(self, owner, repo, ref, path):
        raise NotImplementedError

    async def get_repo_tree(self, owner, repo, ref):
        raise NotImplementedError
