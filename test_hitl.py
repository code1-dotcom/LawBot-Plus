import requests
import json

print('=== 测试高风险问题（应触发HITL审核）===')
response = requests.post(
    'http://127.0.0.1:8000/chat',
    json={'message': '故意杀人罪判刑多少年？死刑能免吗？'}
)
result = response.json()
print('Status:', response.status_code)
print('Response:', json.dumps(result, ensure_ascii=False, indent=2))

# 获取待审核任务
print()
print('=== 获取待审核任务列表 ===')
response2 = requests.get('http://127.0.0.1:8000/hitl/tasks')
tasks = response2.json()
print(f'待审核任务数: {len(tasks)}')
if tasks:
    print(f'第一个任务:')
    print(f"  Task ID: {tasks[0]['task_id']}")
    print(f"  Question: {tasks[0]['user_question'][:50]}...")
    print(f"  Risk Level: {tasks[0]['risk_level']}")
    print(f"  Confidence: {tasks[0]['confidence_score']}")
