path = r'f:\26_01\项目\LawBot\src\agents\workflow.py'
with open(path, 'rb') as f:
    content = f.read()

old = b'return False\n\n        # \xe6\x95\xb0\xe9\x87\x8f\xe9\x97\xa8\xe5\x80\xbe'

new = b'return False\n\n        # \xe8\xb0\x83\xe8\xaf\x95: \xe6\x89\x93\xe5\x8d\xb0 reranked_docs \xe5\x88\x86\xe6\x95\xb0\n        scores = [doc.get("rerank_score", 0) for doc in state.reranked_docs]\n        logger.info("[RelevanceCheck] PASS: top_scores=%s" % scores[:3])\n\n        # \xe6\x95\xb0\xe9\x87\x8f\xe9\x97\xa8\xe5\x80\xbe'

if old in content:
    content = content.replace(old, new)
    with open(path, 'wb') as f:
        f.write(content)
    print('OK')
else:
    print('NOT FOUND')
    # Debug
    idx = content.find(b'return False')
    print('First return False:', repr(content[idx:idx+50]))
