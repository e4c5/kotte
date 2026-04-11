#!/usr/bin/env python3
import json
import subprocess
import sys
import re
from datetime import datetime

def run_gh_command(command):
    try:
        result = subprocess.run(['gh'] + command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running gh command: {e.stderr}", file=sys.stderr)
        return None

def fetch_pr_data(owner, repo, pr_number):
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 50) {
            nodes {
              id
              isResolved
              comments(first: 50) {
                nodes {
                  url
                  path
                  line
                  body
                  author { login }
                  replyTo { id }
                }
              }
            }
          }
          comments(first: 50) {
            nodes {
              url
              body
              author { login }
            }
          }
        }
      }
    }
    """
    variables = {"owner": owner, "repo": repo, "number": int(pr_number)}
    result = run_gh_command(['api', 'graphql', '-f', f'query={query}', '-f', f'owner={owner}', '-f', f'repo={repo}', '-F', f'number={pr_number}'])
    return json.loads(result) if result else None

def decompose_bot_comment(author, body, url):
    items = []
    # Specialized parsing for CodeRabbit/CodeAnt/Viper
    if author in ['coderabbitai', 'codeant-ai', 'viper-review']:
        # Look for sections in <details> blocks or bold headers
        findings = re.findall(r'(?:###|####|\*\*)\s*(.*?)\n(.*?)(?=\n(?:###|####|\*\*)|$)', body, re.DOTALL)
        for title, content in findings:
            if "Actionable" in title or "Nitpick" in title or "Potential issue" in title:
                items.append({
                    "title": title.strip(),
                    "content": content.strip(),
                    "url": url
                })
    
    if not items:
        items.append({"title": "General Comment", "content": body, "url": url})
    return items

def main(pr_url):
    match = re.search(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
    if not match:
        print("Invalid PR URL")
        sys.exit(1)
    
    owner, repo, pr_number = match.groups()
    data = fetch_pr_data(owner, repo, pr_number)
    if not data:
        return

    pr_node = data['data']['repository']['pullRequest']
    all_actions = []

    # Process Review Threads
    for thread in pr_node['reviewThreads']['nodes']:
        if thread['isResolved']: continue
        top_comment = thread['comments']['nodes'][0]
        decomposed = decompose_bot_comment(top_comment['author']['login'], top_comment['body'], top_comment['url'])
        for item in decomposed:
            all_actions.append({
                "url": item['url'],
                "file": top_comment.get('path', 'N/A'),
                "line": top_comment.get('line', 'N/A'),
                "why": item['title'],
                "plan": item['content']
            })

    # Process Issue Comments (Bot Reports)
    for comment in pr_node['comments']['nodes']:
        if comment['author']['login'] in ['coderabbitai', 'codeant-ai', 'viper-review']:
            decomposed = decompose_bot_comment(comment['author']['login'], comment['body'], comment['url'])
            for item in decomposed:
                all_actions.append({
                    "url": item['url'],
                    "file": "Global/Multiple",
                    "line": "N/A",
                    "why": item['title'],
                    "plan": item['content']
                })

    # Write the plan file
    filename = f"review-actions-{pr_number}.md"
    with open(filename, "w") as f:
        f.write(f"# Review Actions for PR #{pr_number}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for i, action in enumerate(all_actions, 1):
            f.write(f"### {i}. {action['why']}\n")
            f.write(f"- **URL**: {action['url']}\n")
            f.write(f"- **File**: {action['file']}:{action['line']}\n")
            f.write(f"- **Plan**: {action['plan']}\n\n")
    
    print(f"Plan generated in {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_pr.py <PR_URL>")
    else:
        main(sys.argv[1])
