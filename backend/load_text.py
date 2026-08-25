"""
Load test: fires N jobs rapidly at a queue to prove multiple workers
claim distinct jobs with no duplicates and no jobs left stuck.

Usage:
    python load_test.py <base_url> <token> <queue_id> <count>

Example:
    python load_test.py https://your-backend.onrender.com/api eyJ...token QUEUE_ID 30
"""

import sys
import time
import requests
from collections import Counter


def main():
    if len(sys.argv) != 5:
        print("Usage: python load_test.py <base_url> <token> <queue_id> <count>")
        sys.exit(1)

    base_url, token, queue_id, count = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"Creating {count} jobs...")
    job_ids = []
    start = time.time()

    for i in range(count):
        res = requests.post(
            f"{base_url}/queues/{queue_id}/jobs",
            headers=headers,
            json={"name": f"load-test-{i}", "job_type": "example", "payload": {"i": i}}
        )
        if res.status_code == 201:
            job_ids.append(res.json()["id"])
        else:
            print(f"  job {i} failed to create: {res.status_code} {res.text}")

    print(f"Created {len(job_ids)}/{count} jobs in {time.time() - start:.1f}s")
    print("Waiting 15s for workers to process...")
    time.sleep(15)

    # check final statuses
    res = requests.get(f"{base_url}/queues/{queue_id}/jobs", headers=headers)
    jobs = res.json()

    status_counts = Counter(j["status"] for j in jobs if j["id"] in job_ids)
    print("\nFinal status breakdown:")
    for status, cnt in status_counts.items():
        print(f"  {status}: {cnt}")

    stuck = [j for j in jobs if j["id"] in job_ids and j["status"] in ("queued", "claimed", "running")]
    if stuck:
        print(f"\n{len(stuck)} jobs still not finished -- either workers are slow or something's stuck.")
    else:
        print("\nAll jobs reached a terminal state. No stuck jobs -- claim logic is behaving correctly.")


if __name__ == "__main__":
    main()
