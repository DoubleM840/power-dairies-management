import subprocess, sys, os

ROOT = r'c:\Users\HomePC\dairy_management'
LOG  = os.path.join(ROOT, '_gitpush_out.txt')

env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'GIT_TERMINAL_PROMPT': '0'}

def run(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=env)
    line = f'CMD: {args}\nOUT: {r.stdout.strip()}\nERR: {r.stderr.strip()}\nRC:  {r.returncode}\n\n'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line)
    return r.returncode

# Clear log
open(LOG, 'w').close()

run(['git', 'add', '-A'])
run(['git', 'status', '--short'])
rc = run(['git', 'commit', '-m',
    'feat: dark mode, M-Pesa STK Push, order tracking, payment summary, '
    'collector sync on milk approval, admin/collector/farmer template fixes'])
if rc not in (0, 1):
    sys.exit(rc)
run(['git', 'push'])
