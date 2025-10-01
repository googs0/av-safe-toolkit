# Naive in-memory rate limiter (for local/demo)
import time
from fastapi import Request, HTTPException

class RateLimiter:
    def __init__(self, limit=60, window=60.0):
        self.limit=limit; self.window=window
        self.bucket={}
    def _key(self, req: Request):
        auth=req.headers.get("authorization") or req.headers.get("Authorization")
        return auth or req.client.host or "anon"
    def __call__(self, req: Request):
        k=self._key(req); now=time.time()
        w=int(now//self.window)
        count,win=self.bucket.get(k,(0,w))
        if w!=win: count=0; win=w
        count+=1; self.bucket[k]=(count,win)
        if count>self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

limiter = RateLimiter(limit=60, window=60.0)
