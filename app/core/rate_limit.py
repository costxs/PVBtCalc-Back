import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core import config


def client_ip(request: Request) -> str:
    if config.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Janela deslizante em memoria, por IP (suficiente para uma unica instancia)."""

    def __init__(self, limit: tuple[int, int]):
        self.max, self.window = limit
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def __call__(self, request: Request):
        now, ip = time.monotonic(), client_ip(request)
        with self._lock:
            q = self._hits[ip]
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.max:
                raise HTTPException(429, "auth.err_rate_limited", headers={"Retry-After": str(self.window)})
            q.append(now)
            if len(self._hits) > 10000:
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
                    del self._hits[k]


auth_limiter = RateLimiter(config.AUTH_RATE_LIMIT)
api_limiter = RateLimiter(config.API_RATE_LIMIT)
