"""Operator-owned policy. Never loaded from a PR branch."""
from dataclasses import dataclass, field
from pathlib import Path
import re
import tomllib

REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
LOGIN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z')


@dataclass
class BotConfig:
    repositories: list[str]
    database: str = 'reviews.sqlite3'
    provider: str = 'gemini'
    model: str = 'gemini-3.1-flash-lite'
    endpoint: str = 'http://127.0.0.1:11434'
    cloud_review: bool = False
    allow_forks: bool = False
    roles: dict[str, list[str]] = field(default_factory=lambda: {'privacy_officer': [], 'model_owner': [], 'engineering': []})
    routing: dict[str, list[str]] = field(default_factory=lambda: {
        'article-4a': ['privacy_officer'], 'article-10': ['privacy_officer', 'model_owner'],
        'annex-iv-2': ['model_owner'], 'article-15': ['model_owner'], 'article-14': ['engineering']})

    def __post_init__(self):
        if not self.repositories or any(not REPO.fullmatch(r) for r in self.repositories):
            raise ValueError('Configure explicit owner/repository names.')
        self.repositories = [r.lower() for r in self.repositories]
        if self.provider not in {'gemini', 'ollama'} or (self.provider == 'gemini' and not self.cloud_review):
            raise ValueError('Choose Ollama or explicitly enable cloud_review for Gemini.')
        if not self.roles or any(not re.fullmatch(r'[a-z_]{1,40}', role) or
                                 (not isinstance(logins, list) or any(not isinstance(login, str) or not LOGIN.fullmatch(login) for login in logins)) for role, logins in self.roles.items()):
            raise ValueError('Roles must contain explicit valid GitHub user logins.')
        if any(not isinstance(prefix, str) or not prefix or any(role not in self.roles for role in roles)
               for prefix, roles in self.routing.items()):
            raise ValueError('Routing must reference configured roles.')

    @classmethod
    def load(cls, path: Path):
        with path.open('rb') as stream:
            return cls(**tomllib.load(stream))

    def required_roles(self, finding: dict) -> list[str]:
        roles = {role for citation in finding['citations'] for prefix, selected in self.routing.items()
                 if citation['section_id'] == prefix or citation['section_id'].startswith(prefix+'-') for role in selected}
        return sorted(roles or ({'engineering'} & self.roles.keys()))

    def actor_roles(self, login: str) -> list[str]:
        return sorted(role for role, users in self.roles.items() if login.lower() in {u.lower() for u in users})
