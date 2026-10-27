"""Strict public-prefix projection and realized direct-target-KO labels."""
from collections import Counter
import hashlib
import re

SLOT=re.compile(r'^p[12]a(?:\:.*)?$',re.I)
ALIAS=re.compile(r'\bp([12])([abc]?):\s*[^|]*',re.I)
BOUNDARY={'move','cant','switch','drag','turn','upkeep','win','tie'}
PUBLIC={'gametype','teamsize','gen','tier','rule','clearpoke','poke','teampreview','start','turn',
        'switch','drag','move','cant','faint','upkeep','swap','detailschange','formechange'}
BLOCK_MOVES={'futuresight','doomdesire','destinybond','perishsong','healingwish','lunardance','explosion','selfdestruct','mistyexplosion','finalgambit'}
FORBIDDEN_REPLAY={'replace','-transform'}
OUTCOMES=['Direct target KO occurred','No direct target KO occurred']


def to_id(s):return re.sub('[^a-z0-9]','',s.lower())
def slot(s):return s.split(':',1)[0].strip().lower()
def fields(line):return line.rstrip('\r').split('|')
def event(line):
    f=fields(line)
    return f[1].lower() if len(f)>1 else ''


def hp(value):
    """Public absolute/percentage numerator only; no hidden-HP inference."""
    m=re.match(r'^(\d+)(?:/(\d+))?(?:\s|$)',value)
    if not m:raise ValueError('unreadable_hp')
    return int(m[1]),int(m[2]) if m[2] else None


def sanitize(line):
    return ALIAS.sub(lambda m:'p'+m[1]+m[2].lower(),line)


def public_prefix(lines,end):
    out=[]
    for l in lines[:end]:
        e=event(l)
        if e in PUBLIC or (e.startswith('-') and e not in {'-message','-hint','-anim','-center'}):
            out.append(sanitize(l))
    return out


def projection(lines,index):
    f=fields(lines[index]);assert f[1].lower()=='move'
    return dict(format='Historical Gen9 OU singles public replay',view='Public spectator view; hidden sets/stats are unknown; public HP is rounded',
        public_history=public_prefix(lines,index),
        proposed_attack={'actor':slot(f[2]),'move':f[3],'target':slot(f[4])},
        cutoff='Immediately before the proposed attack line. Only the attack identity is given as a condition; its outcome is hidden.')


def replay_rejection(lines):
    es={event(l) for l in lines}
    if not {'start','turn'}<=es or not es&{'win','tie'}:return 'incomplete_replay'
    if FORBIDDEN_REPLAY&es:return 'transformed_or_replaced_identity'
    if any('illusion' in l.lower() or 'zoroark' in l.lower() or 'zorua' in l.lower() for l in lines):return 'illusion_possible'
    if not any(l.lower()=='|gametype|singles' for l in lines):return 'not_singles'
    if not any(l.lower()=='|gen|9' for l in lines):return 'not_gen9'
    if any(event(l)=='split' for l in lines):return 'split_private_view'
    return None


def extract(text,move_table):
    lines=text.splitlines();reason=replay_rejection(lines)
    if reason:return [],Counter({reason:1})
    found=[];excluded=Counter();active={};turn=None
    for i,line in enumerate(lines):
        f=fields(line);e=event(line)
        if e=='turn':
            try:turn=int(f[2])
            except (ValueError,IndexError):turn=None
        if e in {'switch','drag'} and len(f)>4:
            active[slot(f[2])]={'species':f[3],'hp':f[4]}
        if e in {'-damage','-heal','-sethp'} and len(f)>3 and slot(f[2]) in active:
            active[slot(f[2])]['hp']=f[3]
        if e=='faint' and len(f)>2 and slot(f[2]) in active:active[slot(f[2])]['hp']='0 fnt'
        if e!='move':continue
        if len(f)<5 or not SLOT.match(f[2]) or not SLOT.match(f[4]):excluded['non_single_target']+=1;continue
        actor,target=slot(f[2]),slot(f[4]);mid=to_id(f[3])
        if actor[:2]==target[:2]:excluded['self_or_ally_target']+=1;continue
        if '[from]' in line.lower():excluded['called_or_reaction_move']+=1;continue
        if mid not in move_table or move_table[mid]['category']=='Status':excluded['unknown_or_status_move']+=1;continue
        if mid in BLOCK_MOVES:excluded['delayed_or_special_ko_move']+=1;continue
        if actor not in active or target not in active or turn is None:excluded['missing_active_context']+=1;continue
        try:pre_hp=hp(active[target]['hp'])[0]
        except ValueError:excluded['unreadable_pre_hp']+=1;continue
        if pre_hp<=0:excluded['already_fainted']+=1;continue
        end=i+1
        while end<len(lines) and event(lines[end]) not in BOUNDARY:end+=1
        if end==len(lines):excluded['unterminated_resolution']+=1;continue
        block=lines[i+1:end];damage=[];faints=[];indirect=[];negative=[];ambiguous=False
        for k,l in enumerate(block,i+1):
            parts=fields(l);kind=event(l)
            if kind=='-damage' and len(parts)>3 and slot(parts[2])==target:
                try:value=hp(parts[3])[0]
                except ValueError:ambiguous=True;continue
                if any(s.lower().startswith('[from]') for s in parts[4:]):indirect.append((k,value))
                else:damage.append((k,value))
            if kind=='faint' and len(parts)>2 and slot(parts[2])==target:faints.append(k)
            if kind=='-miss' and len(parts)>3 and slot(parts[3])==target:negative.append('miss')
            if kind=='-immune' and len(parts)>2 and slot(parts[2])==target:negative.append('immune')
            if kind=='-activate' and len(parts)>3 and slot(parts[2])==target and 'protect' in parts[3].lower():negative.append('protection')
            if kind in {'-ohko','-notarget'}:ambiguous=True
            if any(term in to_id(l) for term in ['destinybond','perish','futuresight','doomdesire','substitute']):ambiguous=True
        if ambiguous:excluded['ambiguous_resolution']+=1;continue
        zero=[k for k,v in damage if v==0]
        if zero:
            if not any(z<q for z in zero for q in faints):excluded['zero_without_faint']+=1;continue
            label=0;outcome_kind='direct_ko'
        elif faints:
            # A later residual KO is not evidence of direct attack lethality; omit the mixed frame.
            excluded['indirect_or_unattributed_target_faint']+=1;continue
        elif damage and damage[-1][1]>0:
            label=1;outcome_kind='direct_hit_survived'
        elif negative:
            label=1;outcome_kind=negative[0]
        else:
            excluded['no_unambiguous_target_outcome']+=1;continue
        state=projection(lines,i)
        found.append(dict(move_index=i,frame_end=end,turn=turn,actor=actor,target=target,move_id=mid,
            state=state,target_index=label,outcome_kind=outcome_kind,
            evidence={'damage_events':damage,'faint_events':faints,'indirect_damage_events':indirect,
                'outcome_frame':[sanitize(l) for l in block],'boundary_event':event(lines[end]),
                'public_hp_before':active[target]['hp'],'hit_count':len(damage),
                'critical_hit':any(event(l)=='-crit' and len(fields(l))>2 and slot(fields(l)[2])==target for l in block)}))
    return found,excluded
