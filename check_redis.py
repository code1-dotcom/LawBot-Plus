import redis, json

r = redis.from_url(
    "redis://:redis_password_2024@192.168.88.108:6379/0",
    decode_responses=True
)

keys = r.keys("lawbot:session:*")
print(f"Found {len(keys)} sessions")

for key in sorted(keys)[-5:]:  # latest 5
    data = r.get(key)
    if data:
        obj = json.loads(data)
        sid = obj.get("session_id", "?")
        msgs = obj.get("messages", [])
        print(f"\n=== {sid} ===")
        for m in msgs:
            if m.get("role") == "assistant":
                print(f"  rewritten_query: {m.get('rewritten_query')}")
                print(f"  tokenized_query: {m.get('tokenized_query')}")
                break
