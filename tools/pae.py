import re
STEP={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
def keymap(ks):
    m={}
    if not ks or ks=='n': return m
    sign=1 if ks[0]=='x' else -1 if ks[0]=='b' else 0
    for ch in ks[1:]:
        if ch in STEP: m[ch]=sign
    return m
def pitches(data,ks=''):
    km=keymap(ks); oc=4; out=[]; acc=None; grace=False; ingroup=False; chord=False
    i=0; s=data
    while i<len(s):
        ch=s[i]
        if ch=="'" or ch==',':
            j=i
            while j<len(s) and s[j]==ch: j+=1
            n=j-i; oc=3+n if ch=="'" else 4-n; i=j; continue
        if ch in '%$@': # clef/key/time change: skip token
            j=i+1
            while j<len(s) and s[j] not in '/ ': j+=1
            if ch=='$': km=keymap(s[i+1:j])
            i=j; continue
        if ch=='x':
            acc=2 if s[i+1:i+2]=='x' else 1; i+=2 if acc==2 else 1; continue
        if ch=='b' and i+1<len(s) and (s[i+1] in STEP or s[i+1]=='b'):
            acc=-2 if s[i+1]=='b' else -1; i+=2 if acc==-2 else 1; continue
        if ch=='n': acc=0; i+=1; continue
        if ch=='q':
            if s[i+1:i+2]=='q': ingroup=True; i+=2; continue
            grace=True; i+=1; continue
        if ch=='r': ingroup=False; i+=1; continue
        if ch=='g': grace=True; i+=1; continue
        if ch=='^': chord=True; i+=1; continue
        if ch in STEP:
            a=acc if acc is not None else km.get(ch,0)
            if not grace and not ingroup and not chord:
                out.append(12*(oc+1)+STEP[ch]+a)
            grace=False; chord=False; acc=None; i+=1; continue
        i+=1
    return out
def intervals(p): return [b-a for a,b in zip(p,p[1:])]
def lcp(a,b):
    n=0
    for x,y in zip(a,b):
        if x!=y: break
        n+=1
    return n
def dedup(p):
    o=[]
    for x in p:
        if not o or o[-1]!=x: o.append(x)
    return o
def sim(p1,p2):
    """notes agreeing from start, ignoring repeated-note differences, transposition-invariant"""
    a,b=dedup(p1),dedup(p2)
    return lcp(intervals(a),intervals(b))+1 if a and b else 0
