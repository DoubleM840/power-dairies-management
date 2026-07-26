import subprocess, sys, os

os.chdir(r'c:\Users\HomePC\dairy_management')

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, **kw)
    out = (r.stdout + r.stderr).strip()
    with open('_gitpush_out.txt', 'a', encoding='utf-8') as f:
        f.write(f'\n--- {" ".join(cmd)} ---\n{out}\nRC={r.returncode}\n')
    return r.returncode, out

# Stage all tracked + new files (respects .gitignore)
run(['git', 'add', '-A'])
run(['git', 'status', '--short'])
rc, out = run(['git', 'commit', '-m',
    'feat: dark mode, M-Pesa STK Push, order tracking, payment summary, '
    'collector sync on milk approval, admin/collector/farmer template fixes'])
if rc not in (0, 1):   # 1 = nothing to commit
    sys.exit(rc)
rc, out = run(['git', 'push'])
with open('_gitpush_out.txt', 'a', encoding='utf-8') as f:
    f.write('\nFINAL RC=' + str(rc) + '\n')
