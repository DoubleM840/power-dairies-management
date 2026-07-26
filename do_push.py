import subprocess, os, sys

ROOT = r'c:\Users\HomePC\dairy_management'
LOG  = os.path.join(ROOT, 'push_out.txt')
env  = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'GIT_TERMINAL_PROMPT': '0'}

def run(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=env)
    entry = f'\n=== {" ".join(args)} ===\n{r.stdout.strip()}\n{r.stderr.strip()}\nRC={r.returncode}\n'
    open(LOG, 'a', encoding='utf-8').write(entry)
    return r.returncode

open(LOG, 'w').close()

run(['git', 'add', '-A'])
run(['git', 'status', '--short'])
rc = run(['git', 'commit', '-m',
    'chore: migrate from Railway to Render — render.yaml, updated settings, Procfile, requirements'])
if rc not in (0, 1):
    sys.exit(rc)
run(['git', 'push'])
