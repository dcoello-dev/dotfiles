import os, pty, time, select, re
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}; env["TERM"]="xterm-256color"
LAB=os.path.expanduser("~/shell-lab/lab")
pid,fd=pty.fork()
if pid==0: os.chdir(os.path.expanduser("~/code")); os.execve(LAB,[LAB],env)
buf=b""
def drain(q,mx=30.0):
    global buf
    s=time.time()
    while time.time()-s<mx:
        r,_,_=select.select([fd],[],[],q)
        if r:
            try: d=os.read(fd,1<<16)
            except OSError: return
            if not d: return
            buf+=d
        else: return
time.sleep(1.2); drain(3.0)
def k(d,q=1.6):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.06)
    drain(q); return buf
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','').replace('\x08','').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"

k(b"hl\n", 5.0)
print("multiline inside hl:")
a = k(b"for i in 1 2 3; do\n", 2.2)
print(f"  {ok('>' in ''.join(ls_(a)))} for..do waits with '>' -> {ls_(a)[-1:]}")
b = k(b"echo n=$i\n", 2.0)
print(f"  {ok('>' in ''.join(ls_(b)))} second line also waits")
c = k(b"done\n", 3.0)
got = ls_(c)
print(f"  {ok('n=1' in got and 'n=2' in got and 'n=3' in got)} runs on 'done' -> {[x for x in got if x.startswith('n=')]}")

print()
d = k(b"echo 'two\n", 2.2)
print(f"  {ok('>' in ''.join(ls_(d)))} unclosed quote waits")
e = k(b"lines'\n", 2.5)
print(f"  {ok(any('two' in x for x in ls_(e)))} closes and runs -> {[x for x in ls_(e) if 'two' in x or 'lines' in x][:2]}")

print()
f_ = k(b"echo pipe |\n", 2.2)
print(f"  {ok('>' in ''.join(ls_(f_)))} trailing pipe waits")
g = k(b"cat\n", 2.5)
print(f"  {ok('pipe' in ' '.join(ls_(g)))} completes -> {[x for x in ls_(g) if 'pipe' in x][:1]}")

print()
h = k(b"echo )\n", 3.5)
print(f"  {ok(any('syntax error' in x or 'unexpected' in x for x in ls_(h)))} 'echo )' is NOT trapped, bash complains")
print(f"       {[x for x in ls_(h) if 'unexpected' in x or 'syntax' in x][:1]}")

print()
i_ = k(b"for x in a b; do\n", 2.2)
j = k(b"\x03", 1.5)            # C-c abandons
kk = k(b"echo after-abort\n", 2.0)
print(f"  {ok('after-abort' in ls_(kk))} C-c abandons the continuation -> {[x for x in ls_(kk) if 'after' in x][:1]}")
k(b"\x04", 1.6)
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
